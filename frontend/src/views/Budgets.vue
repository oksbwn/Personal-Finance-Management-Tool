<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import { useCurrency } from '@/composables/useCurrency'

const { formatAmount } = useCurrency()
const notify = useNotificationStore()

// State
const budgets = ref<any[]>([])
const categories = ref<any[]>([])
const loading = ref(true)
const loadingInsights = ref(false)
const showModal = ref(false)
const insights = ref<any[]>([])

// Month Selection
const now = new Date()
const selectedDate = ref(new Date(now.getFullYear(), now.getMonth(), 1))

const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

const monthYearLabel = computed(() => {
    return `${months[selectedDate.value.getMonth()]} ${selectedDate.value.getFullYear()}`
})

function changeMonth(delta: number) {
    const d = new Date(selectedDate.value)
    d.setMonth(d.getMonth() + delta)
    selectedDate.value = d
    fetchData()
}

function resetToCurrent() {
    selectedDate.value = new Date(now.getFullYear(), now.getMonth(), 1)
    fetchData()
}

const newBudget = ref({
    category: '',
    amount_limit: null as number | null
})

const activeTab = ref<'expense' | 'income'>('expense')

// Metrics
const overallBudget = computed(() => budgets.value.find(b => b.category === 'OVERALL'))
const categoryBudgets = computed(() => {
    const list = budgets.value.filter(b => b.category !== 'OVERALL')
    if (activeTab.value === 'income') return list.filter(b => b.income > 0 || b.excluded > 0)
    // Default to expense
    return list.filter(b => b.spent > 0 || b.excluded > 0 || (b.amount_limit && b.amount_limit > 0))
})

const totalIncome = computed(() => {
    if (overallBudget.value) return Number(overallBudget.value.income || 0)
    return budgets.value
        .filter(b => b.category !== 'OVERALL')
        .reduce((sum, b) => sum + Number(b.income || 0), 0)
})

const totalSpent = computed(() => {
    if (overallBudget.value) return Number(overallBudget.value.spent)
    return categoryBudgets.value.reduce((sum, b) => sum + Number(b.spent), 0)
})

const budgetStatusPrefix = computed(() => {
    if (!overallBudget.value) return ''
    return overallBudget.value.spent > overallBudget.value.amount_limit ? 'Overspent by' : 'Safe Capacity'
})

const modalTitle = computed(() => {
    return newBudget.value.category === 'OVERALL' ? 'Total Monthly Limit' : 'Category Budget'
})

const spendingVelocity = computed(() => {
    const d = new Date()
    const isCurrentMonth = selectedDate.value.getMonth() === d.getMonth() &&
        selectedDate.value.getFullYear() === d.getFullYear()

    if (!isCurrentMonth) return { status: 'neutral', diff: 0, monthProgress: 100 }

    const daysInMonth = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
    const dayOfMonth = d.getDate()
    const monthProgress = (dayOfMonth / daysInMonth) * 100

    if (!overallBudget.value || !overallBudget.value.amount_limit) return { status: 'stable', diff: 0, monthProgress }

    const diff = overallBudget.value.percentage - monthProgress
    let status = 'stable'
    if (diff > 15) status = 'aggressive'
    else if (diff > 5) status = 'warning'

    return { status, diff, monthProgress }
})

const categoryOptions = computed(() => {
    return categories.value.map(c => ({
        label: `${c.icon || '🏷️'} ${c.name}`,
        value: c.name
    }))
})

async function fetchData() {
    loading.value = true
    insights.value = [] // Reset insights on month change
    try {
        const year = selectedDate.value.getFullYear()
        const month = selectedDate.value.getMonth() + 1
        const [budgetRes, catRes] = await Promise.all([
            financeApi.getBudgets(year, month),
            financeApi.getCategories()
        ])
        budgets.value = budgetRes.data
        categories.value = catRes.data
    } catch (e) {
        console.error(e)
        notify.error("Failed to load budgets")
    } finally {
        loading.value = false
    }
}

async function fetchInsights() {
    loadingInsights.value = true
    try {
        const year = selectedDate.value.getFullYear()
        const month = selectedDate.value.getMonth() + 1
        const res = await financeApi.getBudgetsInsights(year, month)
        insights.value = res.data
    } catch (e) {
        notify.error("Failed to generate AI insights")
    } finally {
        loadingInsights.value = false
    }
}

function openSetBudgetModal(isOverall = false) {
    if (isOverall) {
        newBudget.value = { category: 'OVERALL', amount_limit: null }
    } else {
        newBudget.value = { category: '', amount_limit: null }
    }
    showModal.value = true
}

function editBudget(b: any) {
    newBudget.value = {
        category: b.category,
        amount_limit: b.amount_limit
    }
    showModal.value = true
}

async function saveBudget() {
    if (!newBudget.value.category || !newBudget.value.amount_limit) return
    try {
        await financeApi.setBudget(newBudget.value)
        notify.success("Budget saved")
        showModal.value = false
        fetchData()
    } catch (e) {
        notify.error("Failed to save budget")
    }
}

async function deleteBudget(id: string) {
    if (!confirm("Remove this budget?")) return
    try {
        await financeApi.deleteBudget(id)
        notify.success("Budget removed")
        fetchData()
    } catch (e) {
        notify.error("Failed to remove budget")
    }
}

onMounted(() => {
    fetchData()
})
</script>

<template>
    <MainLayout>
        <div class="budgets-view">
            <!-- Premium Header -->
            <div class="page-header-premium">
                <div class="header-left">
                    <h1 class="page-title">Budgets & Activity</h1>
                    <p class="page-subtitle">Personal finance intelligence</p>
                </div>

                <div class="header-actions">
                    <div class="month-selector-premium glass">
                        <button @click="changeMonth(-1)" class="btn-icon-sm">‹</button>
                        <div class="selected-month-display" @click="resetToCurrent">
                            <span class="month-label">{{ monthYearLabel }}</span>
                        </div>
                        <button @click="changeMonth(1)" class="btn-icon-sm">›</button>
                    </div>

                    <button v-if="!overallBudget" class="btn-outline-compact" @click="openSetBudgetModal(true)">
                        + Limit
                    </button>
                    <button class="btn-primary-glow" @click="openSetBudgetModal(false)">
                        + Set Category
                    </button>
                </div>
            </div>

            <div v-if="loading" class="loading-state">
                <div class="loader-spinner"></div>
                <p>Calculating your spending power...</p>
            </div>

            <div v-else class="animate-in">
                <!-- Overall Budget Hero Card (Premium Midnight) -->
                <div v-if="overallBudget" class="overall-premium-card">
                    <div class="card-glass-content">
                        <div class="card-top">
                            <div class="card-main">
                                <div class="card-header-badge">Overall Target</div>
                                <div class="price-row">
                                    <span class="amount-large">{{ formatAmount(overallBudget.spent) }}</span>
                                    <span class="separator">/</span>
                                    <span class="total-limit">{{ overallBudget.amount_limit ?
                                        formatAmount(overallBudget.amount_limit) : '∞' }}</span>
                                </div>
                            </div>
                            <div class="card-actions">
                                <button v-if="overallBudget.budget_id" @click="editBudget(overallBudget)"
                                    class="btn-glass-sq">✏️</button>
                                <button v-else @click="openSetBudgetModal(true)" class="btn-glass-sq">+</button>
                            </div>
                        </div>

                        <div v-if="overallBudget.amount_limit" class="velocity-indicator"
                            :class="spendingVelocity.status">
                            <div class="velocity-icon">
                                <span v-if="spendingVelocity.status === 'aggressive'">⚠️</span>
                                <span v-else-if="spendingVelocity.status === 'warning'">🔔</span>
                                <span v-else-if="spendingVelocity.status === 'stable'">✅</span>
                                <span v-else>📊</span>
                            </div>
                            <div class="velocity-text">
                                <template v-if="spendingVelocity.status === 'aggressive'">
                                    Spending is <strong>{{ spendingVelocity.diff.toFixed(0) }}% ahead</strong> of the
                                    monthly curve.
                                </template>
                                <template v-else-if="spendingVelocity.status === 'warning'">
                                    Slightly above pace. {{ formatAmount(overallBudget.remaining) }} left for the month.
                                </template>
                                <template v-else-if="spendingVelocity.status === 'stable'">
                                    Under control. You are spend-aligned with the month progress.
                                </template>
                                <template v-else>
                                    Monthly activity snapshot.
                                </template>
                            </div>
                        </div>

                        <div v-if="overallBudget.amount_limit" class="progress-container-lg">
                            <div class="progress-bar-bg-lg">
                                <div class="progress-bar-fill-lg"
                                    :style="{ width: Math.min(overallBudget.percentage, 100) + '%' }" :class="{
                                        'warning': overallBudget.percentage > 80 && overallBudget.percentage <= 100,
                                        'danger': overallBudget.percentage > 100
                                    }"></div>
                                <!-- Month progress vertical line marker -->
                                <div v-if="spendingVelocity.status !== 'neutral'" class="month-marker"
                                    :style="{ left: spendingVelocity.monthProgress + '%' }">
                                    <span class="marker-label">Today</span>
                                </div>
                            </div>
                            <div class="progress-meta">
                                <span class="percentage-badge" :class="{ 'over': overallBudget.percentage > 100 }">
                                    {{ overallBudget.percentage?.toFixed(1) }}% Utilized
                                </span>
                                <span class="remaining-text">
                                    {{ budgetStatusPrefix }}: <strong>{{ formatAmount(Math.abs(overallBudget.remaining))
                                        }}</strong>
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="mesh-blob blob-1"></div>
                    <div class="mesh-blob blob-2"></div>
                </div>

                <div class="ai-insights-row animate-in">
                    <div class="insight-label-group">
                        <span class="ai-sparkle">✨</span>
                        <span class="insight-heading">AI Intelligence</span>

                        <button v-if="insights.length === 0" @click="fetchInsights" class="btn-ai-generate"
                            :disabled="loadingInsights">
                            <span v-if="loadingInsights" class="btn-spinner-sm"></span>
                            {{ loadingInsights ? 'Analyzing...' : 'Generate Insights' }}
                        </button>
                        <button v-else @click="fetchInsights" class="btn-ai-refresh" :disabled="loadingInsights"
                            title="Refresh Insights">
                            <span v-if="loadingInsights" class="btn-spinner-sm"></span>
                            <span v-else>🔄</span>
                        </button>
                    </div>

                    <div v-if="insights.length > 0" class="insight-cards-scroll">
                        <div v-for="insight in insights" :key="insight.id" class="mini-insight-card glass"
                            :class="insight.type">
                            <span class="insight-icon">{{ insight.icon }}</span>
                            <div class="insight-body">
                                <h4 class="insight-title">{{ insight.title }}</h4>
                                <p class="insight-content">{{ insight.content }}</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Summary Grid -->
                <div class="summary-widgets-budget">
                    <div class="mini-stat-card glass h-glow-success">
                        <div class="stat-top">
                            <span class="stat-label">Income In</span>
                            <span class="stat-icon-bg green">💰</span>
                        </div>
                        <div class="stat-value">{{ formatAmount(totalIncome) }}</div>
                    </div>
                    <div class="mini-stat-card glass h-glow-danger">
                        <div class="stat-top">
                            <span class="stat-label">Total Outflow</span>
                            <span class="stat-icon-bg red">💸</span>
                        </div>
                        <div class="stat-value">{{ formatAmount(totalSpent) }}</div>
                    </div>
                    <div class="mini-stat-card glass h-glow-primary">
                        <div class="stat-top">
                            <span class="stat-label">Net Balance</span>
                            <span class="stat-icon-bg blue">⚖️</span>
                        </div>
                        <div class="stat-value" :class="{ 'negative': (totalIncome - totalSpent) < 0 }">
                            {{ formatAmount(totalIncome - totalSpent) }}
                        </div>
                    </div>
                    <div v-if="overallBudget?.total_excluded || overallBudget?.excluded_income"
                        class="mini-stat-card glass" style="border-left: 4px solid #94a3b8;">
                        <div class="stat-top">
                            <span class="stat-label">Excluded Items</span>
                            <span class="stat-icon-bg gray text-muted" style="filter: grayscale(1);">🚫</span>
                        </div>
                        <div class="stat-value"
                            style="color: #64748b; font-size: 1.1rem; display: flex; flex-direction: column; gap: 2px;">
                            <span v-if="overallBudget.total_excluded > 0" title="Excluded Expenses">
                                {{ formatAmount(overallBudget.total_excluded) }} Out
                            </span>
                            <span v-if="overallBudget.excluded_income > 0" style="color: #10b981; font-size: 0.9rem;"
                                title="Excluded Income">
                                +{{ formatAmount(overallBudget.excluded_income) }} In
                            </span>
                        </div>
                    </div>
                </div>

                <div class="section-header-row">
                    <h2 class="section-title">Category Intelligence</h2>
                    <div class="tabs-premium-compact glass">
                        <button v-for="t in (['expense', 'income'] as const)" :key="t" @click="activeTab = t"
                            class="tab-btn-sm" :class="{ active: activeTab === t }">
                            {{ t.charAt(0).toUpperCase() + t.slice(1) }}
                        </button>
                    </div>
                </div>
                <div class="budget-grid">
                    <div v-for="b in categoryBudgets" :key="b.category" class="glass-card budget-card"
                        :style="{ borderLeft: `4px solid ${b.color || '#3B82F6'}` }">
                        <div class="card-top">
                            <div class="card-main">
                                <div class="card-icon-wrapper"
                                    :style="{ background: (b.color || '#3B82F6') + '15', color: b.color || '#3B82F6' }">
                                    {{ b.icon || '🏷️' }}
                                </div>
                                <span class="card-name">{{ b.category }}</span>
                            </div>
                            <div class="card-actions">
                                <button v-if="b.budget_id" @click="editBudget(b)" class="btn-ghost-sm"
                                    title="Edit Budget">✏️</button>
                                <button v-else @click="openSetBudgetModal(false); newBudget.category = b.category"
                                    class="btn-ghost-sm" title="Set Limit">+</button>

                                <button v-if="b.budget_id" @click="deleteBudget(b.budget_id)"
                                    class="btn-ghost-sm danger" title="Delete Budget">✕</button>
                            </div>
                        </div>

                        <!-- Activity Breakdown -->
                        <div class="activity-row-premium" v-if="b.spent > 0 || b.income > 0 || b.excluded > 0">
                            <div class="act-item income" v-if="b.income > 0">
                                <span class="act-label">Received</span>
                                <span class="act-val success">+{{ formatAmount(b.income) }}</span>
                            </div>
                            <div class="act-item expense" v-if="b.spent > 0">
                                <span class="act-label">Spent</span>
                                <span class="act-val">{{ formatAmount(b.spent) }}</span>
                            </div>
                            <div class="act-item excluded" v-if="b.excluded > 0">
                                <span class="act-label">Excluded</span>
                                <span class="act-val" style="color: #94a3b8; font-size: 0.85rem;">🚫 {{
                                    formatAmount(b.excluded)
                                    }}</span>
                            </div>
                        </div>

                        <div v-if="b.amount_limit" class="progress-section">
                            <div class="progress-bar-bg-sm">
                                <div class="progress-bar-fill-sm" :style="{
                                    width: Math.min(b.percentage, 100) + '%',
                                    backgroundColor: b.percentage > 100 ? '#ef4444' : (b.percentage > 80 ? '#f59e0b' : (b.color || '#3B82F6'))
                                }"></div>
                            </div>
                            <div class="remaining-footer" :class="{ 'over': b.remaining < 0 }">
                                <span class="pct-sub">{{ b.percentage.toFixed(0) }}% of {{ formatAmount(b.amount_limit)
                                    }}</span>
                                <span class="rem-sub">{{ b.remaining >= 0 ? `${formatAmount(b.remaining)} left` :
                                    `${formatAmount(Math.abs(b.remaining))} over` }}</span>
                            </div>
                        </div>
                        <div v-else class="no-limit-info">
                            <div class="info-pill-sm">No limit set for this category</div>
                        </div>

                        <!-- Decorative BG Icon -->
                        <div class="card-bg-icon">{{ b.icon || '🏷️' }}</div>
                    </div>

                    <div v-if="categoryBudgets.length === 0" class="empty-card" @click="openSetBudgetModal(false)">
                        <span class="empty-plus">+</span>
                        <p>No activity recorded in this period</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Budget Modal -->
        <div v-if="showModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ modalTitle }}</h2>
                    <button class="btn-icon-circle" @click="showModal = false">✕</button>
                </div>

                <form @submit.prevent="saveBudget" class="form-compact">
                    <div class="form-group" v-if="newBudget.category !== 'OVERALL'">
                        <label class="form-label">Category</label>
                        <CustomSelect v-model="newBudget.category" :options="categoryOptions"
                            placeholder="Select Category" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Monthly Limit (₹)</label>
                        <div class="amount-input-wrapper">
                            <span class="input-prefix">₹</span>
                            <input type="number" v-model="newBudget.amount_limit" class="form-input" required
                                placeholder="5,000" />
                        </div>
                    </div>

                    <div class="modal-footer">
                        <button type="button" @click="showModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Budget</button>
                    </div>
                </form>
            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
.budgets-view {
    padding-bottom: 4rem;
}

/* Premium Header Styling */
.page-header-premium {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    gap: 1.5rem;
}

.header-left {
    flex: 1;
}

.page-title {
    font-size: 1.75rem;
    font-weight: 800;
    color: #1e293b;
    margin: 0;
    letter-spacing: -0.02em;
}

.page-subtitle {
    font-size: 0.875rem;
    color: #64748b;
    margin: 0.25rem 0 0 0;
}

.header-center {
    display: flex;
    justify-content: center;
}

.month-selector-premium {
    display: flex;
    align-items: center;
    background: white;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    gap: 1rem;
}

.selected-month-display {
    cursor: pointer;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
    transition: background 0.2s;
}

.selected-month-display:hover {
    background: #f1f5f9;
}

.month-label {
    font-weight: 700;
    color: #1e293b;
    font-size: 0.9375rem;
}

.btn-icon-sm {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: none;
    background: #f8fafc;
    color: #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.25rem;
    transition: all 0.2s;
}

.btn-icon-sm:hover {
    background: #e2e8f0;
    color: #1e293b;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

/* Premium Midnight Card */
.overall-premium-card {
    background: #0f172a;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 1.25rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
    color: white;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.card-glass-content {
    position: relative;
    z-index: 10;
}

.card-header-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.price-row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
}

.amount-large {
    font-size: 2.25rem;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: -0.05em;
}

.separator {
    font-size: 1.25rem;
    color: #475569;
}

.total-limit {
    font-size: 1.25rem;
    font-weight: 600;
    color: #94a3b8;
}

.velocity-indicator {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 0.875rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.8125rem;
}

.velocity-indicator.aggressive {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.2);
}

.velocity-indicator.warning {
    background: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.2);
}

.velocity-icon {
    font-size: 1.25rem;
}

.velocity-text {
    color: #cbd5e1;
    line-height: 1.5;
}

.velocity-text strong {
    color: #f8fafc;
    font-weight: 700;
}

.progress-container-lg {
    margin-top: 2rem;
}

.progress-bar-bg-lg {
    height: 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    position: relative;
    overflow: visible;
}

.progress-bar-fill-lg {
    height: 100%;
    background: #6366f1;
    border-radius: 6px;
    transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: 0 0 15px rgba(99, 102, 241, 0.3);
}

.progress-bar-fill-lg.warning {
    background: #f59e0b;
    box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
}

.progress-bar-fill-lg.danger {
    background: #ef4444;
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
}

.month-marker {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    background: white;
    z-index: 5;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
}

.marker-label {
    position: absolute;
    top: -20px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    white-space: nowrap;
}

.progress-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1rem;
}

.percentage-badge {
    padding: 0.25rem 0.75rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
}

.percentage-badge.over {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
}

.remaining-text {
    font-size: 0.875rem;
    color: #94a3b8;
}

.remaining-text strong {
    color: white;
}

.mesh-blob {
    position: absolute;
    filter: blur(80px);
    opacity: 0.15;
    border-radius: 50%;
    z-index: 1;
}

.blob-1 {
    width: 400px;
    height: 400px;
    background: #3b82f6;
    top: -150px;
    right: -100px;
}

.blob-2 {
    width: 350px;
    height: 350px;
    background: #6366f1;
    bottom: -100px;
    left: -100px;
}

/* AI Insights Styling */
.ai-insights-row {
    margin-bottom: 2rem;
}

.insight-label-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.875rem;
}

.ai-sparkle {
    font-size: 1rem;
}

.insight-heading {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #4f46e5;
}

.insight-cards-scroll {
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    padding-bottom: 0.5rem;
    scrollbar-width: none;
}

.insight-cards-scroll::-webkit-scrollbar {
    display: none;
}

.mini-insight-card {
    min-width: 280px;
    flex: 1;
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border-radius: 1rem;
    background: white;
    border: 1px solid #e2e8f0;
    transition: all 0.2s;
}

.mini-insight-card:hover {
    transform: translateY(-2px);
    border-color: #cbd5e1;
}

.mini-insight-card.danger {
    border-left: 4px solid #ef4444;
}

.mini-insight-card.warning {
    border-left: 4px solid #f59e0b;
}

.mini-insight-card.success {
    border-left: 4px solid #10b981;
}

.mini-insight-card.info {
    border-left: 4px solid #3b82f6;
}

.insight-icon {
    font-size: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.insight-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0 0 0.25rem 0;
}

.insight-content {
    font-size: 0.8125rem;
    color: #64748b;
    margin: 0;
    line-height: 1.4;
}

.btn-ai-generate {
    margin-left: auto;
    background: #4f46e50d;
    color: #4f46e5;
    border: 1px solid #4f46e522;
    padding: 0.375rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.btn-ai-generate:hover {
    background: #4f46e51a;
    border-color: #4f46e544;
}

.btn-ai-generate:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-ai-refresh {
    margin-left: auto;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.875rem;
    opacity: 0.5;
    transition: all 0.2s;
    display: flex;
    align-items: center;
}

.btn-ai-refresh:hover:not(:disabled) {
    opacity: 1;
    transform: rotate(45deg);
}

.btn-spinner-sm {
    width: 14px;
    height: 14px;
    border: 2px solid #4f46e533;
    border-top-color: #4f46e5;
    border-radius: 50%;
    animation: insight-spin 0.6s linear infinite;
}

@keyframes insight-spin {
    to {
        transform: rotate(360deg);
    }
}

/* Summary Grid */
.summary-widgets-budget {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    margin-bottom: 2.5rem;
}

.mini-stat-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1rem;
    transition: all 0.2s;
}

.mini-stat-card:hover {
    border-color: #cbd5e1;
    transform: translateY(-2px);
}

.stat-value.negative {
    color: #ef4444;
}

/* Category Grid Header */
.section-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
}

.section-title {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    margin: 0;
}

.tabs-premium-compact {
    display: flex;
    background: #f1f5f9;
    padding: 0.25rem;
    border-radius: 0.75rem;
    gap: 0.25rem;
}

.tab-btn-sm {
    padding: 0.375rem 0.75rem;
    border-radius: 0.5rem;
    border: none;
    background: transparent;
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn-sm:hover {
    color: #1e293b;
}

.tab-btn-sm.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.budget-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
}

.glass-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1.25rem;
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
}

.card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    position: relative;
    z-index: 2;
    margin-bottom: 1rem;
}

.card-main {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.card-name {
    font-size: 1rem;
    font-weight: 700;
    color: #1e293b;
}

.card-icon-wrapper {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 0.625rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}

.activity-row-premium {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1rem;
    position: relative;
    z-index: 2;
}

.act-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 0.375rem 0.625rem;
    border-radius: 0.625rem;
    background: #f8fafc;
}

.act-label {
    font-size: 0.6rem;
    text-transform: uppercase;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.025em;
}

.act-val {
    font-size: 1rem;
    font-weight: 700;
    color: #1e293b;
}

.act-val.success {
    color: #10b981;
}

.progress-section {
    position: relative;
    z-index: 2;
}

.progress-bar-bg-sm {
    height: 6px;
    background: #f1f5f9;
    border-radius: 3px;
    margin-bottom: 0.75rem;
    overflow: hidden;
}

.progress-bar-fill-sm {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease;
}

.remaining-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
}

.remaining-footer.over {
    color: #ef4444;
}

.pct-sub {
    opacity: 0.8;
}

.no-limit-info {
    position: relative;
    z-index: 2;
}

.info-pill-sm {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    background: #f1f5f9;
    color: #64748b;
    border-radius: 99px;
    font-size: 0.7rem;
    font-weight: 600;
}

.card-bg-icon {
    position: absolute;
    bottom: -0.75rem;
    right: -0.75rem;
    font-size: 5rem;
    opacity: 0.04;
    transform: rotate(-12deg);
    pointer-events: none;
    z-index: 0;
    filter: grayscale(100%);
}

.btn-glass-sq {
    width: 2.25rem;
    height: 2.25rem;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 0.75rem;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    backdrop-filter: blur(10px);
    transition: all 0.2s;
    font-size: 1rem;
}

.btn-glass-sq:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
}

.btn-ghost-sm {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 0.75rem;
    border: none;
    background: #f8fafc;
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-ghost-sm:hover {
    background: #f1f5f9;
    color: #4b5563;
}

.btn-ghost-sm.danger:hover {
    background: #fef2f2;
    color: #ef4444;
}

/* Buttons */
.btn-primary-glow {
    padding: 0.625rem 1.25rem;
    background: #4f46e5;
    color: white;
    border-radius: 0.75rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    transition: all 0.2s;
}

.btn-primary-glow:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(79, 70, 229, 0.3);
}

.btn-outline-compact {
    padding: 0.625rem 1.25rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-outline-compact:hover {
    border-color: #cbd5e1;
    background: #f8fafc;
}

.animate-in {
    animation: slideUp 0.5s ease-out forwards;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(15px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@media (max-width: 768px) {
    .page-header-premium {
        flex-direction: column;
        align-items: stretch;
    }

    .header-actions {
        justify-content: stretch;
    }

    .summary-widgets-budget {
        grid-template-columns: 1fr;
    }

    .amount-large {
        font-size: 2.25rem;
    }
}
</style>
