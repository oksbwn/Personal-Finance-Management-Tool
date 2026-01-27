<template>
    <MainLayout>
        <div class="loans-container animate-in">
            <div class="page-header">
                <div class="header-left">
                    <h1 class="page-title">Loans</h1>
                </div>
                <div class="header-actions">
                    <button @click="generatePortfolioInsights" class="btn-compact btn-secondary"
                        :disabled="insightLoading">
                        <Sparkles :size="14" />
                        {{ insightLoading ? 'Analyzing...' : 'AI Analysis' }}
                    </button>
                    <button @click="openAddModal" class="btn-compact btn-primary">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2">
                            <path d="M12 5v14M5 12h14" />
                        </svg>
                        Add Loan
                    </button>
                </div>
            </div>

            <!-- Summary Stats -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="stat-card">
                    <h3 class="stat-label">Total Outstanding</h3>
                    <p class="stat-value">
                        {{ formatCurrency(totalOutstanding) }}
                    </p>
                </div>
                <div class="stat-card">
                    <h3 class="stat-label">Monthly EMI Commitment</h3>
                    <p class="stat-value">
                        {{ formatCurrency(totalMonthlyEmi) }}
                    </p>
                </div>
                <div class="stat-card">
                    <h3 class="stat-label">Active Loans</h3>
                    <p class="stat-value">
                        {{ loans.length }}
                    </p>
                </div>
            </div>

            <!-- Loans Grid -->
            <div v-if="loading" class="text-center py-12">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            </div>

            <div v-else-if="loans.length === 0"
                class="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700">
                <p class="text-gray-500 dark:text-gray-400 text-lg">No active loans found.</p>
                <button @click="openAddModal" class="mt-4 text-blue-600 hover:text-blue-700 font-medium">
                    Add your first loan
                </button>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div v-for="loan in loans" :key="loan.id" @click="viewDetails(loan.id)" class="loan-card">
                    <div class="loan-accent"></div>

                    <div class="loan-card-header">
                        <div>
                            <h3 class="loan-name">{{ loan.name }}</h3>
                            <p class="loan-meta">Due: {{ getNextDueDate(loan.next_emi_date) }}</p>
                        </div>
                        <span class="loan-badge">
                            {{ loan.interest_rate }}% APR
                        </span>
                    </div>

                    <div class="loan-type-tag">
                        <span class="mr-1">{{ getLoanIcon(loan.loan_type) }}</span>
                        {{ loan.loan_type?.replace('_', ' ') || 'LOAN' }}
                    </div>

                    <div class="progress-container">
                        <div class="progress-label-row">
                            <span class="text-gray-500">Progress</span>
                            <span class="font-medium text-gray-700">{{ loan.progress_percentage }}%</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" :style="{ width: loan.progress_percentage + '%' }"></div>
                        </div>
                    </div>

                    <div class="loan-stats-footer">
                        <div>
                            <p class="footer-stat-label">Outstanding</p>
                            <p class="footer-stat-value">{{ formatCurrency(loan.outstanding_balance) }}</p>
                        </div>
                        <div class="text-right">
                            <p class="footer-stat-label">EMI Amount</p>
                            <p class="footer-stat-value">{{ formatCurrency(loan.emi_amount) }}</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Add Loan Modal -->
            <div v-if="showModal" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 550px;">
                    <div class="modal-header">
                        <h2 class="modal-title">Add New Loan</h2>
                        <button class="btn-icon" @click="closeModal">✕</button>
                    </div>

                    <form @submit.prevent="submitLoan" style="padding-top: 1rem;">
                        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
                            <div class="form-group">
                                <label class="form-label">Loan Name</label>
                                <input v-model="form.name" type="text" required class="form-input"
                                    placeholder="e.g. Home Loan">
                            </div>

                            <div class="form-group">
                                <label class="form-label">Loan Type</label>
                                <CustomSelect v-model="form.loan_type" :options="loanTypeOptions"
                                    placeholder="Select Loan Type" />
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div class="form-group">
                                    <label class="form-label">Principal Amount</label>
                                    <input v-model.number="form.principal_amount" @input="calculateEmi" type="number"
                                        required class="form-input">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Interest Rate (%)</label>
                                    <input v-model.number="form.interest_rate" @input="calculateEmi" type="number"
                                        step="0.01" required class="form-input">
                                </div>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div class="form-group">
                                    <label class="form-label">Tenure (Months)</label>
                                    <input v-model.number="form.tenure_months" @input="calculateEmi" type="number"
                                        required class="form-input">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Start Date</label>
                                    <input v-model="form.start_date" type="date" required class="form-input">
                                </div>
                            </div>

                            <div class="form-group">
                                <label class="form-label">EMI Due Day (1-31)</label>
                                <input v-model.number="form.emi_date" type="number" min="1" max="31" required
                                    class="form-input">
                            </div>

                            <div
                                style="background: #eff6ff; padding: 1rem; border-radius: 0.75rem; border: 1px solid #dbeafe;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-size: 0.875rem; color: #1e40af; font-weight: 600;">Calculated
                                        EMI</span>
                                    <span style="font-size: 1.125rem; color: #1e40af; font-weight: 800;">{{
                                        formatCurrency(form.emi_amount) }}</span>
                                </div>
                            </div>
                        </div>

                        <div class="modal-footer">
                            <button type="button" @click="closeModal" class="btn btn-outline"
                                style="min-width: 100px;">Cancel</button>
                            <button type="submit" class="btn btn-primary" style="min-width: 140px;">Create Loan</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- AI Insights Modal -->
            <div v-if="showInsightModal" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 700px;">
                    <div class="modal-header">
                        <h2 class="modal-title" style="display: flex; align-items: center; gap: 0.5rem;">
                            <Sparkles class="text-blue-500" />
                            Debt Portfolio Strategy
                        </h2>
                        <button class="btn-icon" @click="showInsightModal = false">✕</button>
                    </div>

                    <div v-if="insightLoading" class="text-center py-12">
                        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                        <p class="mt-4 text-gray-500">Consulting AI advisor...</p>
                    </div>

                    <div v-else class="portfolio-insight-content markdown-body" v-html="renderedInsights"
                        style="max-height: 60vh; overflow-y: auto; padding-right: 1rem;">
                    </div>

                    <div class="modal-footer" style="margin-top: 1.5rem;">
                        <button @click="showInsightModal = false" class="btn btn-primary">Got it, thanks!</button>
                    </div>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import CustomSelect from '@/components/CustomSelect.vue'
import { financeApi as api } from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { useCurrency } from '@/composables/useCurrency'
import { Sparkles } from 'lucide-vue-next'
import { marked } from 'marked'

const router = useRouter()
const notificationStore = useNotificationStore()
const { formatAmount } = useCurrency()
const loading = ref(true)
const loans = ref<any[]>([])
const showModal = ref(false)
const showInsightModal = ref(false)
const insightLoading = ref(false)
const portfolioInsights = ref('')

const form = reactive({
    name: '',
    principal_amount: 0,
    interest_rate: 0,
    tenure_months: 12,
    start_date: new Date().toISOString().split('T')[0],
    emi_date: 5,
    emi_amount: 0,
    loan_type: 'HOME_LOAN'
})

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

const calculateEmi = () => {
    const p = form.principal_amount
    const r = (form.interest_rate / 12) / 100
    const n = form.tenure_months

    if (p > 0 && r > 0 && n > 0) {
        // EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
        const emi = (p * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1)
        form.emi_amount = Math.round(emi * 100) / 100
    } else {
        form.emi_amount = 0
    }
}

const totalOutstanding = computed(() => {
    return loans.value.reduce((sum, loan) => sum + (loan.outstanding_balance || 0), 0)
})

const totalMonthlyEmi = computed(() => {
    return loans.value.reduce((sum, loan) => sum + (loan.emi_amount || 0), 0)
})

const formatCurrency = (amount: any) => formatAmount(amount)

const renderedInsights = computed(() => {
    return portfolioInsights.value ? marked(portfolioInsights.value) : ''
})

const getNextDueDate = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    })
}

const fetchLoans = async () => {
    try {
        const response = await api.getLoans()
        loans.value = response.data
    } catch (e) {
        console.error("Failed to fetch loans", e)
    } finally {
        loading.value = false
    }
}

const openAddModal = () => {
    // Reset form
    form.name = ''
    form.principal_amount = 0
    form.interest_rate = 0
    form.tenure_months = 12
    form.start_date = new Date().toISOString().split('T')[0]
    form.emi_date = 5
    form.emi_date = 5
    form.emi_amount = 0
    form.loan_type = 'HOME_LOAN'
    showModal.value = true
}

const closeModal = () => {
    showModal.value = false
}

const submitLoan = async () => {
    try {
        // We might need to add createLoan to financeApi if not there, but let's use direct post for now or assume it exists
        // Actually, let's use the explicit endpoint to be safe
        await api.createLoan(form)
        notificationStore.success("Loan created successfully!")
        closeModal()
        fetchLoans()
    } catch (e) {
        console.error("Failed to create loan", e)
        notificationStore.error("Failed to create loan. Please check your inputs.")
    }
}

const generatePortfolioInsights = async () => {
    if (loans.value.length === 0) {
        notificationStore.error("Add some loans first to analyze them.")
        return
    }

    showInsightModal.value = true
    insightLoading.value = true
    try {
        // We'll call the explicit endpoint
        const res = await api.getPortfolioInsights()
        portfolioInsights.value = res.data.insights
    } catch (e) {
        console.error("Failed to generate insights", e)
        notificationStore.error("AI Analysis failed. Please try again.")
        showInsightModal.value = false
    } finally {
        insightLoading.value = false
    }
}

const viewDetails = (id: string) => {
    router.push(`/loans/${id}`)
}

onMounted(() => {
    fetchLoans()
})
</script>

<style scoped>
.loans-container {
    width: 100%;
    margin: 0 auto;
    padding-bottom: 3rem;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.page-title {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--color-text-main);
    margin: 0;
}

.header-actions {
    display: flex;
    gap: 1rem;
}

/* Reuse dashboard styles if possible, else define here */
.grid {
    display: grid;
}

.grid-cols-1 {
    grid-template-columns: repeat(1, minmax(0, 1fr));
}

@media (min-width: 768px) {
    .md\:grid-cols-2 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .md\:grid-cols-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (min-width: 1024px) {
    .lg\:grid-cols-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

.gap-6 {
    gap: 1.5rem;
}

.mb-8 {
    margin-bottom: 2rem;
}

.stat-card {
    background: white;
    border-radius: 1rem;
    padding: 1.5rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--color-border);
}

.stat-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-muted);
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-main);
    margin-top: 0.5rem;
}

/* Loan Card Styles */
.loan-card {
    background: white;
    border-radius: 1rem;
    padding: 1.5rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--color-border);
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
}

.loan-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.loan-accent {
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: var(--color-primary);
}

.loan-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
}

.loan-name {
    font-weight: 700;
    font-size: 1.125rem;
    color: var(--color-text-main);
}

.loan-meta {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-top: 0.25rem;
}

.loan-badge {
    background: var(--color-primary-light);
    color: var(--color-primary);
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.25rem 0.625rem;
    border-radius: 2rem;
}

.loan-type-tag {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--color-text-muted);
    background: var(--color-background);
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    margin-bottom: 1rem;
}

.progress-container {
    margin-bottom: 1.5rem;
}

.progress-label-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    margin-bottom: 0.375rem;
}

.progress-bar-bg {
    height: 8px;
    background: var(--color-background);
    border-radius: 2rem;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    background: var(--color-primary);
    border-radius: 2rem;
    transition: width 1s ease-out;
}

.loan-stats-footer {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
}

.footer-stat-label {
    font-size: 0.65rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.025em;
}

.footer-stat-value {
    font-weight: 700;
    color: var(--color-text-main);
    font-size: 0.95rem;
}

/* Modal form adjustments */
.btn-compact {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.8125rem;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--color-primary);
    color: white;
}

.btn-primary:hover {
    background: var(--color-primary-dark);
}

.btn-secondary {
    background: white;
    color: var(--color-primary);
    border: 1px solid var(--color-primary-light);
}

.btn-secondary:hover {
    background: var(--color-primary-light);
}

.portfolio-insight-content {
    line-height: 1.6;
}

.portfolio-insight-content :deep(h1),
.portfolio-insight-content :deep(h2),
.portfolio-insight-content :deep(h3) {
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
    font-weight: 700;
}

.portfolio-insight-content :deep(p) {
    margin-bottom: 1rem;
}

.portfolio-insight-content :deep(ul) {
    padding-left: 1.5rem;
    margin-bottom: 1rem;
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
</style>
