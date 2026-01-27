<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useFinanceStore } from '@/stores/finance'
import { financeApi, aiApi } from '@/api/client'
import { useCurrency } from '@/composables/useCurrency'
import BaseChart from '@/components/BaseChart.vue'
import BudgetHistoryChart from '@/components/BudgetHistoryChart.vue'
import CustomSelect from '@/components/CustomSelect.vue'
import { marked } from 'marked'

const store = useFinanceStore()
const { formatAmount } = useCurrency()

const activeTab = ref<'analytics' | 'recurring'>('analytics')

// Filters
const selectedTimeRange = ref('this-month')
const startDate = ref('')
const endDate = ref('')
const selectedAccount = ref('')
const selectedTrendCategory = ref('')
const trendView = ref<'daily' | 'monthly'>('daily')

const timeRangeOptions = [
    { label: 'All Time', value: 'all' },
    { label: 'Today', value: 'today' },
    { label: 'This Week', value: 'this-week' },
    { label: 'This Month', value: 'this-month' },
    { label: 'Last Month', value: 'last-month' },
    { label: 'Custom Range', value: 'custom' }
]

// Data for Analytics
const transactions = ref<any[]>([])
const analyticsMetrics = ref<any>(null)
const forecastData = ref<any[]>([])
const budgets = ref<any[]>([])
const budgetHistory = ref<any[]>([])
const aiInsights = ref<string>('')
const generatingAI = ref(false)
const loading = ref(false)
const showExcludedDetails = ref(false)

onMounted(async () => {
    await store.fetchAll()
    handleTimeRangeChange('this-month') // Initial fetch via handler
})

function handleTimeRangeChange(val: string) {
    const now = new Date()
    const start = new Date()
    const end = new Date()

    startDate.value = ''
    endDate.value = ''

    if (val === 'today') {
        start.setHours(0, 0, 0, 0)
        end.setHours(23, 59, 59, 999)
        startDate.value = start.toISOString().split('T')[0]
        endDate.value = end.toISOString().split('T')[0]
    } else if (val === 'this-week') {
        const day = now.getDay()
        const diff = now.getDate() - day + (day === 0 ? -6 : 1)
        start.setDate(diff)
        start.setHours(0, 0, 0, 0)
        startDate.value = start.toISOString().split('T')[0]
    } else if (val === 'this-month') {
        start.setDate(1)
        start.setHours(0, 0, 0, 0)
        startDate.value = start.toISOString().split('T')[0]
    } else if (val === 'last-month') {
        start.setMonth(start.getMonth() - 1)
        start.setDate(1)
        start.setHours(0, 0, 0, 0)
        end.setMonth(end.getMonth())
        end.setDate(0)
        end.setHours(23, 59, 59, 999)
        startDate.value = start.toISOString().split('T')[0]
        endDate.value = end.toISOString().split('T')[0]
    }

    fetchAnalyticsData()
}

async function fetchAnalyticsData() {
    loading.value = true
    try {
        const params = {
            start_date: startDate.value,
            end_date: endDate.value,
            account_id: selectedAccount.value || undefined
        }

        const [txnRes, metricsRes, forecastRes, budgetRes, historyRes] = await Promise.all([
            financeApi.getTransactions(params.account_id, 1, 1000, params.start_date || undefined, params.end_date || undefined),
            financeApi.getMetrics(params.account_id, params.start_date || undefined, params.end_date || undefined),
            financeApi.getForecast(params.account_id),
            financeApi.getBudgets(),
            financeApi.getBudgetHistory(6)
        ])
        transactions.value = txnRes.data.items
        analyticsMetrics.value = metricsRes.data
        forecastData.value = forecastRes.data
        budgets.value = budgetRes.data
        budgetHistory.value = historyRes.data
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

async function generateAIInsights() {
    generatingAI.value = true
    try {
        const timeContext = selectedTimeRange.value === 'custom'
            ? `from ${startDate.value} to ${endDate.value}`
            : `for ${selectedTimeRange.value.replace('-', ' ')}`

        const velocity = budgetHistory.value.length > 0 ? `Spending velocity is currently showing a ${overallBudget.value?.percentage > 80 ? 'HIGH' : 'STABLE'} trend relative to the monthly cycle.` : ''

        const res = await aiApi.generateSummaryInsights({
            ...analyticsMetrics.value,
            budgets: budgets.value.map(b => ({
                category: b.category,
                limit: b.amount_limit,
                spent: b.spent,
                percent: b.percentage,
                status: b.percentage > 100 ? 'EXCEEDED' : (b.percentage > 80 ? 'CRITICAL' : 'OK')
            })),
            velocity_context: velocity,
            timeframe_filter: timeContext,
            account_filtered: selectedAccount.value ? "Yes" : "No"
        })
        aiInsights.value = res.data.insights
    } catch (e) {
        console.error(e)
        aiInsights.value = "Failed to generate insights. Ensure AI settings are configured."
    } finally {
        generatingAI.value = false
    }
}

const accountOptions = computed(() => {
    return store.accounts.map(a => ({ label: a.name, value: a.id }))
})

const overallBudget = computed(() => budgets.value.find(b => b.category === 'OVERALL'))

// --- Analytics Computed Logic ---
function formatTypeLabel(type: string) {
    const labels: Record<string, string> = {
        'BANK': 'Bank', 'CREDIT_CARD': 'Card', 'LOAN': 'Loan', 'WALLET': 'Cash', 'INVESTMENT': 'Invest'
    }
    return labels[type] || type
}

const analyticsData = computed(() => {
    const data = transactions.value || []
    let income = 0
    let expense = 0
    let excludedExpense = 0
    let excludedIncome = 0
    const catMap: Record<string, number> = {}
    const excludedCatMap: Record<string, number> = {}
    const dateMap: Record<string, number> = {}
    const merchantMap: Record<string, number> = {}
    const accountMap: Record<string, number> = {}
    const typeMap: Record<string, number> = {}
    let weekendSpend = 0
    let weekdaySpend = 0

    // Fetch credit limit info from store accounts
    let totalLimit = 0
    let totalConsumed = 0
    store.accounts.forEach(acc => {
        if (acc.type === 'CREDIT_CARD' && acc.credit_limit) {
            totalLimit += Number(acc.credit_limit)
            totalConsumed += Number(acc.balance)
        }
    })

    data.forEach(t => {
        const amt = Number(t.amount)
        const isExpense = amt < 0
        const isTransfer = t.is_transfer === true
        const isExcluded = t.exclude_from_reports === true
        const absAmt = Math.abs(amt)

        if (isExcluded || isTransfer) {
            if (isExpense) excludedExpense += absAmt
            else excludedIncome += absAmt

            const cat = t.category || (isTransfer ? 'Transfer' : 'Uncategorized')
            excludedCatMap[cat] = (excludedCatMap[cat] || 0) + absAmt
            return
        }

        if (!isExpense) income += absAmt
        else {
            expense += absAmt
            // Categories
            const cat = t.category || 'Uncategorized'
            catMap[cat] = (catMap[cat] || 0) + absAmt

            // Merchants
            const merchant = t.recipient || 'Unknown'
            merchantMap[merchant] = (merchantMap[merchant] || 0) + absAmt

            // Accounts
            const accName = store.getAccountName(t.account_id)
            accountMap[accName] = (accountMap[accName] || 0) + absAmt

            // Account Type
            const acc = store.accounts.find(a => a.id === t.account_id)
            if (acc) {
                const label = formatTypeLabel(acc.type)
                typeMap[label] = (typeMap[label] || 0) + absAmt
            }

            // Patterns
            if (t.date) {
                const day = new Date(t.date).getDay()
                if (day === 0 || day === 6) weekendSpend += absAmt
                else weekdaySpend += absAmt
            }
        }

        const dateKey = t.date ? t.date.split('T')[0] : 'Unknown'
        if (isExpense) dateMap[dateKey] = (dateMap[dateKey] || 0) + absAmt
    })

    const toSortedArray = (map: Record<string, number>) => {
        return Object.entries(map).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name, value }))
    }

    return {
        income,
        expense,
        excludedExpense,
        excludedIncome,
        net: income - expense,
        categories: Object.entries(catMap).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({
            name, value, color: store.getCategoryColor(name), icon: store.getCategoryIcon(name)
        })),
        excludedCategories: Object.entries(excludedCatMap).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({
            name, value, color: store.getCategoryColor(name), icon: store.getCategoryIcon(name)
        })),
        merchants: toSortedArray(merchantMap).slice(0, 5),
        accounts: toSortedArray(accountMap),
        types: toSortedArray(typeMap),
        credit: {
            limit: totalLimit,
            consumed: totalConsumed,
            available: totalLimit - totalConsumed,
            percent: totalLimit > 0 ? (totalConsumed / totalLimit * 100) : 0
        },
        patterns: {
            weekend: weekendSpend,
            weekday: weekdaySpend,
            weekendPercent: expense > 0 ? (weekendSpend / expense * 100) : 0,
            weekdayPercent: expense > 0 ? (weekdaySpend / expense * 100) : 0
        },
        count: data.length
    }
})

// --- Chart Data Preparations ---
const categoryOptions = computed(() => {
    return [{ label: 'All Categories', value: '' }, ...store.categories.map(c => ({ label: c.name, value: c.name }))]
})

const filteredTrendData = computed(() => {
    const txns = transactions.value.filter(t => {
        if (t.is_transfer || t.exclude_from_reports) return false
        if (Number(t.amount) >= 0) return false
        if (selectedTrendCategory.value && t.category !== selectedTrendCategory.value) return false
        return true
    })

    const map: Record<string, number> = {}
    txns.forEach(t => {
        const key = trendView.value === 'daily'
            ? t.date.split('T')[0]
            : t.date.slice(0, 7) // YYYY-MM
        map[key] = (map[key] || 0) + Math.abs(Number(t.amount))
    })

    return Object.entries(map)
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([label, value]) => ({ label, value }))
})

const trendChartData = computed(() => ({
    labels: filteredTrendData.value.map(d => trendView.value === 'daily' ? d.label.slice(5) : d.label),
    datasets: [{
        label: selectedTrendCategory.value || 'All Spending',
        data: filteredTrendData.value.map(d => d.value),
        borderColor: selectedTrendCategory.value ? store.getCategoryColor(selectedTrendCategory.value) : '#6366f1',
        backgroundColor: (selectedTrendCategory.value ? store.getCategoryColor(selectedTrendCategory.value) : '#6366f1') + '20',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: selectedTrendCategory.value ? store.getCategoryColor(selectedTrendCategory.value) : '#6366f1'
    }]
}))


const heatmapData = computed(() => {
    const hours = Array.from({ length: 24 }, (_, i) => i)
    const activeCats = analyticsData.value.categories.slice(0, 8).map(c => c.name)

    // category -> hour -> amount
    const grid: Record<string, Record<number, number>> = {}
    activeCats.forEach(cat => {
        grid[cat] = {}
        hours.forEach(h => grid[cat][h] = 0)
    })

    transactions.value.forEach(t => {
        if (Number(t.amount) >= 0 || t.is_transfer) return
        if (!activeCats.includes(t.category)) return

        const date = new Date(t.date)
        const hour = date.getHours()
        if (grid[t.category]) {
            grid[t.category][hour] += Math.abs(Number(t.amount))
        }
    })

    // Find max for scaling
    let max = 0
    Object.values(grid).forEach(hMap => {
        Object.values(hMap).forEach(val => { if (val > max) max = val })
    })

    return { grid, categories: activeCats, hours, max }
})

const merchantChartData = computed(() => ({
    labels: analyticsData.value.merchants.map(m => m.name),
    datasets: [{
        label: 'Spending',
        data: analyticsData.value.merchants.map(m => m.value),
        backgroundColor: '#6366f1',
        borderRadius: 6,
        borderSkipped: false,
    }]
}))

const categoryChartData = computed(() => ({
    labels: analyticsData.value.categories.map(c => c.name),
    datasets: [{
        data: analyticsData.value.categories.map(c => c.value),
        backgroundColor: analyticsData.value.categories.map(c => c.color || '#3B82F6'),
        hoverOffset: 4
    }]
}))

const forecastChartData = computed(() => ({
    labels: forecastData.value.map(d => d.date.split('T')[0].slice(5)),
    datasets: [{
        label: 'Projected Balance',
        data: forecastData.value.map(d => d.balance),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0
    }]
}))

// --- Recurring Logic ---
const showAddModal = ref(false)

const newRecurrence = ref({
    name: '',
    amount: 0,
    category: '',
    account_id: '',
    frequency: 'MONTHLY',
    start_date: new Date().toISOString().slice(0, 10),
    type: 'DEBIT',
    exclude_from_reports: false
})

async function saveRecurrence() {
    try {
        await financeApi.createRecurringTransaction({
            ...newRecurrence.value,
            next_run_date: newRecurrence.value.start_date
        })
        showAddModal.value = false
        await store.fetchRecurring()
    } catch (e) {
        console.error(e)
    }
}

function deleteRecurrence(id: string) {
    if (!confirm("Stop this subscription?")) return;
    financeApi.deleteRecurring(id).then(() => store.fetchRecurring())
}

const frequencyOptions = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']

</script>

<template>
    <MainLayout>
        <div class="page-header">
            <div class="header-left">
                <h1 class="page-title">Insights</h1>
                <div class="header-tabs">
                    <button class="tab-btn" :class="{ active: activeTab === 'analytics' }"
                        @click="activeTab = 'analytics'">
                        Analytics
                    </button>
                    <button class="tab-btn" :class="{ active: activeTab === 'recurring' }"
                        @click="activeTab = 'recurring'">
                        Recurring
                    </button>
                </div>
                <span class="transaction-count">{{ analyticsData.count }} records analyzed</span>
            </div>
            <div class="header-actions">
                <CustomSelect v-if="activeTab === 'analytics'" v-model="selectedAccount"
                    :options="[{ label: 'All Accounts', value: '' }, ...accountOptions]" placeholder="All Accounts"
                    @update:modelValue="fetchAnalyticsData" class="account-select" />

                <button v-if="activeTab === 'recurring'" @click="showAddModal = true" class="btn-compact btn-primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14" />
                    </svg>
                    Add Subscription
                </button>
            </div>
        </div>

        <div class="filter-bar" v-if="activeTab === 'analytics'">
            <div class="filter-main">
                <div class="filter-group">
                    <span class="filter-label">Time Range:</span>
                    <div class="range-pill-group">
                        <button v-for="opt in timeRangeOptions" :key="opt.value" class="range-pill"
                            :class="{ active: selectedTimeRange === opt.value }"
                            @click="selectedTimeRange = opt.value; handleTimeRangeChange(opt.value)">
                            {{ opt.label }}
                        </button>
                    </div>
                </div>

                <div class="filter-divider" v-if="selectedTimeRange === 'custom'"></div>

                <div class="filter-group animate-in" v-if="selectedTimeRange === 'custom'">
                    <input type="date" v-model="startDate" class="date-input" @change="fetchAnalyticsData" />
                    <span class="filter-separator">to</span>
                    <input type="date" v-model="endDate" class="date-input" @change="fetchAnalyticsData" />
                </div>
            </div>

            <button v-if="startDate || endDate" class="btn-link"
                @click="selectedTimeRange = 'all'; handleTimeRangeChange('all')">
                Reset
            </button>
        </div>

        <div class="content-container">
            <!-- ANALYTICS TAB -->
            <div v-if="activeTab === 'analytics'" class="analytics-layout">
                <!-- AI Insight Card -->
                <div class="ai-card" :class="{ 'is-loading': generatingAI }">
                    <div class="ai-card-content">
                        <div class="ai-header">
                            <div class="ai-title-left">
                                <div class="ai-sparkle-icon">✨</div>
                                <div class="ai-title-group">
                                    <h3 class="ai-card-title">AI Financial Intelligence</h3>
                                    <p class="ai-card-subtitle">Personalized spending vectors and optimization strategy
                                    </p>
                                </div>
                            </div>
                            <button @click="generateAIInsights" :disabled="generatingAI" class="ai-btn-glass">
                                <svg v-if="!generatingAI" width="14" height="14" viewBox="0 0 24 24" fill="none"
                                    stroke="currentColor" stroke-width="2.5">
                                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    <path d="M9 12l2 2 4-4" />
                                </svg>
                                {{ generatingAI ? 'Analyzing...' : 'Refresh Insights' }}
                            </button>
                        </div>

                        <div v-if="aiInsights" class="ai-insight-box custom-scrollbar">
                            <div class="ai-insight-text markdown-body" v-html="marked(aiInsights)"></div>
                        </div>
                        <div v-else-if="generatingAI" class="ai-loading-skeleton">
                            <div class="shimmer-line"></div>
                            <div class="shimmer-line w-3/4"></div>
                            <div class="shimmer-line w-1/2"></div>
                        </div>
                        <p v-else class="ai-card-description">
                            Generate smart insights from your spending patterns, upcoming bills and financial goals.
                        </p>
                    </div>
                    <!-- Mesh blobs for premium feel -->
                    <div class="mesh-blob blob-1"></div>
                    <div class="mesh-blob blob-2"></div>
                    <div class="mesh-blob blob-3"></div>
                </div>

                <!-- Summary Cards -->
                <div class="summary-cards">
                    <div class="summary-card income">
                        <div class="card-icon">📥</div>
                        <div class="card-content">
                            <span class="card-label">Total Income</span>
                            <span class="card-value">{{ formatAmount(analyticsData.income) }}</span>
                            <span class="card-trend text-emerald-600">↑ 12% vs last period</span>
                        </div>
                    </div>
                    <div class="summary-card expense">
                        <div class="card-icon">💸</div>
                        <div class="card-content">
                            <span class="card-label">Total Expenses</span>
                            <span class="card-value">{{ formatAmount(analyticsData.expense) }}</span>
                            <span class="card-trend text-rose-600">↓ 5% vs last period</span>
                        </div>
                    </div>
                    <div class="summary-card net">
                        <div class="card-icon">⚖️</div>
                        <div class="card-content">
                            <span class="card-label">Net Balance</span>
                            <span class="card-value">{{ formatAmount(analyticsData.net) }}</span>
                            <span class="card-trend text-indigo-600">Healthy trend</span>
                        </div>
                    </div>
                </div>

                <div v-if="analyticsData.excludedExpense > 0 || analyticsData.excludedIncome > 0"
                    class="excluded-info-banner animate-in"
                    :style="`margin-bottom: 2rem; background: #f8fafc; border: 1px dashed #cbd5e1; padding: 1.25rem; border-radius: 1.25rem; cursor: pointer; transition: all 0.2s ease; ${showExcludedDetails ? 'border-style: solid; border-color: #94a3b8; background: white;' : ''}`"
                    @click="showExcludedDetails = !showExcludedDetails">
                    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                            <span style="font-size: 1.5rem;">🚫</span>
                            <div>
                                <p style="margin: 0; font-size: 0.875rem; font-weight: 600; color: #475569;">
                                    Some transactions are hidden from these charts
                                </p>
                                <p style="margin: 0; font-size: 0.75rem; color: #64748b;">
                                    {{ showExcludedDetails ? `Category breakdown of hidden items:` :
                                        `You have marked certain items to be excluded from reports and analytics.` }}
                                </p>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 1rem;">
                            <div style="text-align: right;">
                                <span v-if="analyticsData.excludedExpense > 0"
                                    style="font-size: 0.8125rem; font-weight: 700; color: #94a3b8; margin-left: 1rem;">
                                    −{{ formatAmount(analyticsData.excludedExpense) }} Exp
                                </span>
                                <span v-if="analyticsData.excludedIncome > 0"
                                    style="font-size: 0.8125rem; font-weight: 700; color: #10b981; margin-left: 1rem;">
                                    +{{ formatAmount(analyticsData.excludedIncome) }} Inc
                                </span>
                            </div>
                            <span style="font-size: 0.75rem; color: #94a3b8; transition: transform 0.2s ease;"
                                :style="showExcludedDetails ? 'transform: rotate(180deg)' : ''">
                                🔽
                            </span>
                        </div>
                    </div>

                    <!-- Details Breakdown -->
                    <div v-if="showExcludedDetails" class="excluded-details animate-in"
                        style="margin-top: 1.25rem; border-top: 1px solid #f1f5f9; padding-top: 1rem; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem;">
                        <div v-for="cat in analyticsData.excludedCategories" :key="cat.name"
                            style="display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 0.5rem 0.75rem; border-radius: 0.75rem; border: 1px solid #e2e8f0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem; overflow: hidden;">
                                <span style="font-size: 1rem;">{{ cat.icon || '🏷️' }}</span>
                                <span
                                    style="font-size: 0.75rem; font-weight: 600; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{
                                        cat.name }}</span>
                            </div>
                            <span style="font-size: 0.75rem; font-weight: 700; color: #64748b;">{{
                                formatAmount(cat.value) }}</span>
                        </div>
                    </div>
                </div>

                <!-- Charts Section -->
                <div class="analytics-grid">
                    <div class="analytics-card">
                        <h3 class="card-title">Spending by Category</h3>
                        <div class="chart-box">
                            <BaseChart type="doughnut" :data="categoryChartData" :height="250" />
                        </div>
                    </div>

                    <div class="analytics-card">
                        <h3 class="card-title">Top Merchants</h3>
                        <div class="chart-box">
                            <BaseChart type="bar" :data="merchantChartData" :height="250" :options="{
                                indexAxis: 'y',
                                plugins: { legend: { display: false } },
                                scales: { x: { grid: { display: false } }, y: { grid: { display: false } } }
                            }" />
                        </div>
                    </div>

                    <div class="analytics-card full-width">
                        <div class="card-header-flex">
                            <h3 class="card-title">Spending Trends</h3>
                            <div class="card-controls">
                                <div class="toggle-group">
                                    <button :class="{ active: trendView === 'daily' }"
                                        @click="trendView = 'daily'">Day</button>
                                    <button :class="{ active: trendView === 'monthly' }"
                                        @click="trendView = 'monthly'">Month</button>
                                </div>
                                <CustomSelect v-model="selectedTrendCategory" :options="categoryOptions"
                                    placeholder="All Categories" class="mini-select" />
                            </div>
                        </div>
                        <div class="chart-box-large">
                            <BaseChart v-if="filteredTrendData.length > 0" type="line" :data="trendChartData"
                                :height="400" />
                            <div v-else class="empty-chart-state">No data for this filter</div>
                        </div>
                    </div>

                    <div class="analytics-card full-width">
                        <h3 class="card-title">Future Balance Forecast (30 Days)</h3>
                        <div class="chart-box relative">
                            <BaseChart v-if="forecastData.length > 0" type="line" :data="forecastChartData"
                                :height="250" />
                            <div v-else class="empty-chart-state">Calculating...</div>
                        </div>
                        <div class="forecast-footer">
                            <div class="forecast-info">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2">
                                    <circle cx="12" cy="12" r="10" />
                                    <path d="M12 16v-4M12 8h.01" />
                                </svg>
                                Forecast factors in upcoming subscriptions and average spending velocity
                            </div>
                            <div class="forecast-net">
                                Est. Net Change: {{formatAmount(analyticsData.net +
                                    (store.recurringTransactions.reduce((acc, t) => acc + (t.type === 'DEBIT' ? -t.amount :
                                        t.amount), 0)))}}
                            </div>
                        </div>
                    </div>

                    <BudgetHistoryChart v-if="budgetHistory.length > 0" :history="budgetHistory" />

                    <!-- Heatmap Section -->
                    <div class="analytics-card full-width">
                        <h3 class="card-title">Spending Heatmap (Category vs Hour)</h3>
                        <div class="heatmap-container">
                            <div class="heatmap-header">
                                <div class="heatmap-cat-label"></div>
                                <div v-for="h in heatmapData.hours" :key="h" class="hour-label">{{ h }}h</div>
                            </div>
                            <div v-for="cat in heatmapData.categories" :key="cat" class="heatmap-row">
                                <div class="heatmap-cat-label text-truncate">{{ cat }}</div>
                                <div v-for="h in heatmapData.hours" :key="h" class="heatmap-cell-wrapper">
                                    <div class="heatmap-cell" :style="{
                                        opacity: heatmapData.grid[cat][h] > 0 ? 0.2 + (heatmapData.grid[cat][h] / heatmapData.max * 0.8) : 0.05,
                                        backgroundColor: store.getCategoryColor(cat) || '#4f46e5'
                                    }" :title="`${cat} at ${h}h: ${formatAmount(heatmapData.grid[cat][h])}`"></div>
                                </div>
                            </div>
                        </div>
                        <div class="heatmap-footer">
                            <div class="heatmap-legend">
                                <span class="legend-label">Low Spending</span>
                                <div class="legend-gradient"></div>
                                <span class="legend-label">High Spending</span>
                            </div>
                            <span class="heatmap-hint text-xs">Higher opacity indicates more spending activity in that
                                hour.</span>
                        </div>
                    </div>

                    <!-- Category Breakdown List -->
                    <div class="analytics-card">
                        <h3 class="card-title">Spending Breakdown</h3>
                        <div class="category-list">
                            <div v-for="cat in analyticsData.categories.slice(0, 6)" :key="cat.name"
                                class="category-item-box">
                                <div class="item-header">
                                    <span class="item-name">{{ cat.name }}</span>
                                    <span class="item-value">{{ formatAmount(cat.value) }}</span>
                                </div>
                                <div class="progress-bar-bg">
                                    <div class="progress-bar-fill"
                                        :style="{ width: `${(cat.value / analyticsData.expense * 100)}%`, backgroundColor: cat.color }">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Top Merchants -->
                    <div class="analytics-card">
                        <h3 class="card-title">Top Merchants</h3>
                        <div class="merchant-list">
                            <div v-for="m in analyticsData.merchants" :key="m.name" class="merchant-item">
                                <span class="item-name">{{ m.name }}</span>
                                <span class="item-value">{{ formatAmount(m.value) }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- RECURRING TAB -->
            <div v-else class="recurring-layout">
                <div class="recurring-grid">
                    <div v-for="rec in store.recurringTransactions" :key="rec.id"
                        class="recurring-card flex justify-between items-center group">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-50 text-2xl">
                                {{ store.getCategoryIcon(rec.category) }}
                            </div>
                            <div>
                                <h3 class="font-bold text-gray-900">{{ rec.name }}</h3>
                                <p class="text-xs text-gray-500 font-medium">Next: {{ new
                                    Date(rec.next_run_date).toLocaleDateString() }} • {{ rec.frequency }}
                                    <span v-if="rec.exclude_from_reports" class="ml-2 text-rose-500 font-bold"
                                        title="Excluded from reports">🚫 Excluded</span>
                                </p>
                            </div>
                        </div>
                        <div class="text-right">
                            <p class="font-bold text-gray-900">{{ formatAmount(rec.amount) }}</p>
                            <button @click="deleteRecurrence(rec.id)"
                                class="text-xs text-red-500 opacity-0 group-hover:opacity-100 transition-opacity mt-1">Cancel</button>
                        </div>
                    </div>
                </div>

                <div v-if="store.recurringTransactions.length === 0"
                    class="py-20 text-center bg-white rounded-2xl border border-dashed border-gray-300">
                    <p class="text-2xl mb-2">📫</p>
                    <h3 class="font-bold text-gray-900">No active subscriptions</h3>
                    <p class="text-sm text-gray-500">Add your recurring bills to see them here.</p>
                </div>
            </div>
        </div>

        <!-- Standard Add Modal -->
        <div v-if="showAddModal" class="modal-overlay-global" @click.self="showAddModal = false">
            <div class="modal-global">
                <div class="modal-header">
                    <h3 class="modal-title">New Subscription</h3>
                    <button @click="showAddModal = false" class="btn-icon">✕</button>
                </div>

                <div class="space-y-4">
                    <div class="form-group">
                        <label class="form-label">Name</label>
                        <input v-model="newRecurrence.name" type="text" class="form-input"
                            placeholder="Netflix, Rent, etc.">
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="form-group">
                            <label class="form-label">Amount</label>
                            <input v-model="newRecurrence.amount" type="number" class="form-input">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Frequency</label>
                            <select v-model="newRecurrence.frequency" class="form-select">
                                <option v-for="f in frequencyOptions" :key="f" :value="f">{{ f }}</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="form-group">
                            <label class="form-label">Start Date</label>
                            <input v-model="newRecurrence.start_date" type="date" class="form-input">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Account</label>
                            <select v-model="newRecurrence.account_id" class="form-select">
                                <option v-for="a in store.accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <select v-model="newRecurrence.category" class="form-select">
                            <option v-for="c in store.categories" :key="c.id" :value="c.name">{{ c.icon }} {{ c.name }}
                            </option>
                        </select>
                    </div>

                    <div class="form-group flex items-center gap-2 p-3 bg-rose-50 rounded-xl border border-rose-100">
                        <input type="checkbox" v-model="newRecurrence.exclude_from_reports" id="excludeRec"
                            class="w-4 h-4 text-rose-600 focus:ring-rose-500 border-gray-300 rounded">
                        <label for="excludeRec" class="text-sm font-bold text-rose-800 cursor-pointer">Exclude generated
                            transactions from reports</label>
                    </div>
                </div>

                <div class="modal-footer">
                    <button @click="showAddModal = false" class="btn btn-outline">Cancel</button>
                    <button @click="saveRecurrence" class="btn btn-primary">Start Subscription</button>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
/* --- Design Language Consistenty (Ported from Transactions.vue) --- */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
}

.account-select {
    min-width: 240px;
}

.account-select :deep(.select-trigger) {
    padding: 0.5rem 0.875rem;
    font-size: 0.875rem;
    display: flex;
    align-items: center;
}

.header-left {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
}

.page-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}

.transaction-count {
    font-size: 0.875rem;
    color: #6b7280;
    font-weight: 400;
}

.header-tabs {
    display: flex;
    gap: 0.25rem;
    background: #f3f4f6;
    padding: 0.25rem;
    border-radius: 0.5rem;
    margin: 0 1rem;
}

.tab-btn {
    padding: 0.375rem 1rem;
    border: none;
    background: transparent;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.account-select-header {
    min-width: 180px;
    padding: 0.5rem 2rem 0.5rem 0.75rem;
    font-size: 0.875rem;
    border-radius: 0.5rem;
}

.header-divider {
    width: 1px;
    height: 1.5rem;
    background: #e5e7eb;
    margin: 0 0.5rem;
}

.content-container {
    padding: 0;
}

.summary-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.5rem;
    margin-bottom: 1.5rem;
}

.summary-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    display: flex;
    align-items: center;
    gap: 1.25rem;
}

.card-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 0.75rem;
    font-size: 1.5rem;
}

.card-content {
    flex: 1;
}

.card-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.card-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
}

.card-trend {
    font-size: 0.625rem;
    font-weight: 700;
    margin-top: 0.25rem;
    display: block;
}

.income .card-icon {
    background: #ecfdf5;
    color: #059669;
}

.expense .card-icon {
    background: #fef2f2;
    color: #dc2626;
}

.net .card-icon {
    background: #eff6ff;
    color: #4f46e5;
}

.income .card-value {
    color: #059669;
}

.expense .card-value {
    color: #dc2626;
}

.analytics-layout,
.recurring-layout {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.analytics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.5rem;
    padding-bottom: 2rem;
}

.analytics-card.full-width {
    grid-column: span 2;
}

.analytics-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.card-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #111827;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1.25rem;
}

.ai-card {
    background: #0f172a;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: white;
    padding: 1.75rem 2.25rem;
    border-radius: 1.5rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.ai-card.is-loading .ai-insight-box {
    opacity: 0.5;
    filter: blur(1px);
}

.ai-card-content {
    position: relative;
    z-index: 10;
}

.ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
    gap: 1.5rem;
}

.ai-title-left {
    display: flex;
    align-items: center;
    gap: 1.25rem;
}

.ai-sparkle-icon {
    font-size: 2rem;
    background: rgba(255, 255, 255, 0.1);
    width: 3.5rem;
    height: 3.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 1rem;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.ai-card-title {
    font-size: 1.125rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.01em;
    color: #f8fafc;
}

.ai-card-subtitle {
    font-size: 0.8125rem;
    color: #94a3b8;
    margin: 4px 0 0 0;
    font-weight: 400;
}

.ai-insight-box {
    background: rgba(15, 23, 42, 0.4);
    padding: 1.5rem;
    border-radius: 1.25rem;
    backdrop-filter: blur(8px);
    margin-bottom: 0.5rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    max-height: 400px;
    overflow-y: auto;
}

.ai-insight-text {
    font-size: 0.9375rem;
    line-height: 1.7;
    color: #e2e8f0;
}

.ai-btn-glass {
    background: rgba(255, 255, 255, 0.05);
    color: white;
    padding: 0.625rem 1.25rem;
    border-radius: 0.75rem;
    font-weight: 600;
    font-size: 0.8125rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 0.625rem;
    white-space: nowrap;
}

.ai-btn-glass:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
}

.ai-card-description {
    font-size: 0.875rem;
    color: #94a3b8;
    margin: 1rem 0;
    max-width: 500px;
}

/* Mesh Blobs - Toned Down */
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

.blob-3 {
    width: 250px;
    height: 250px;
    background: #1e40af;
    top: 10%;
    left: 20%;
}

/* Skeleton */
.ai-loading-skeleton {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.shimmer-line {
    height: 1rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
}

.shimmer-line::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
    0% {
        transform: translateX(-100%);
    }

    100% {
        transform: translateX(100%);
    }
}

.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 10px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
}

.markdown-body :deep(h4) {
    font-size: 1rem;
    font-weight: 700;
    margin: 1rem 0 0.5rem 0;
    color: white;
}

.markdown-body :deep(p) {
    margin-bottom: 0.75rem;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
    padding-left: 1.25rem;
    margin-bottom: 0.75rem;
}

.markdown-body :deep(li) {
    margin-bottom: 0.375rem;
}

.markdown-body :deep(strong) {
    font-weight: 700;
    color: white;
}

.forecast-footer {
    margin-top: 1rem;
    padding: 1rem;
    background: #f9fafb;
    border-radius: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #f3f4f6;
}

.forecast-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: #6b7280;
}

.forecast-net {
    font-weight: 700;
    font-size: 0.875rem;
    color: #111827;
}

.item-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.25rem;
}

.empty-chart-state {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    font-size: 0.875rem;
}

.ai-card-description {
    font-size: 0.875rem;
    margin-bottom: 1.5rem;
    color: rgba(255, 255, 255, 0.9);
}

.ai-card-decoration {
    position: absolute;
    right: -5rem;
    bottom: -5rem;
    width: 20rem;
    height: 20rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    filter: blur(60px);
}

.ai-btn-white {
    background: white;
    color: #4f46e5;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-weight: 600;
    font-size: 0.875rem;
    transition: all 0.2s;
}

.ai-btn-white:hover {
    background: #f9fafb;
}

.category-list,
.merchant-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.category-item,
.merchant-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.item-name {
    font-size: 0.875rem;
    color: #374151;
    font-weight: 500;
}

.item-value {
    font-size: 0.875rem;
    font-weight: 700;
    color: #111827;
}

.progress-bar-bg {
    height: 0.5rem;
    background: #f3f4f6;
    border-radius: 999px;
    margin-top: 0.375rem;
}

.progress-bar-fill {
    height: 100%;
    background: #4f46e5;
    border-radius: 999px;
}

.recurring-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
}

.recurring-card {
    background: white;
    padding: 1.25rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
}

/* Animations */
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

/* --- Filter Bar (Ported from Transactions.vue) --- */
.filter-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 0.625rem 1rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    margin-bottom: 1.25rem;
}

.filter-main {
    display: flex;
    align-items: center;
    gap: 1.25rem;
}

.filter-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.filter-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}

.range-pill-group {
    display: flex;
    gap: 0.375rem;
    background: #f3f4f6;
    padding: 2px;
    border-radius: 0.5rem;
    height: 36px;
    box-sizing: border-box;
    align-items: center;
}

.range-pill {
    padding: 0 0.75rem;
    height: 32px;
    border: none;
    background: transparent;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: #4b5563;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
    display: flex;
    align-items: center;
}

.range-pill:hover:not(.active) {
    color: #111827;
    background: #e5e7eb;
}

.range-pill.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.chart-box {
    height: 250px;
    margin-top: 1rem;
}

.chart-box-large {
    height: 400px;
    margin-top: 1rem;
}

.card-header-flex {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.card-controls {
    display: flex;
    gap: 0.75rem;
    align-items: center;
}

.mini-select {
    width: 160px;
}

.mini-select :deep(.select-trigger) {
    padding: 0.25rem 0.625rem;
    height: 32px;
    font-size: 0.75rem;
    background: white;
}

.mini-select :deep(.select-dropdown) {
    font-size: 0.75rem;
}

.toggle-group {
    display: flex;
    background: #f3f4f6;
    padding: 2px;
    border-radius: 0.375rem;
}

.toggle-group button {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    border: none;
    background: transparent;
    border-radius: 0.25rem;
    cursor: pointer;
    color: #6b7280;
    font-weight: 500;
}

.toggle-group button.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

/* Heatmap Styles */
.heatmap-container {
    overflow-x: auto;
    padding: 1rem 0;
}

.heatmap-header,
.heatmap-row {
    display: grid;
    grid-template-columns: 120px repeat(24, 1fr);
    gap: 2px;
    min-width: 800px;
}

.hour-label {
    font-size: 0.65rem;
    color: #9ca3af;
    text-align: center;
}

.heatmap-cat-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: #4b5563;
    padding-right: 0.5rem;
    display: flex;
    align-items: center;
}

.heatmap-cell-wrapper {
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.heatmap-cell {
    width: 100%;
    height: 100%;
    border-radius: 2px;
    transition: transform 0.2s;
}

.heatmap-cell:hover {
    transform: scale(1.2);
    z-index: 10;
}

.heatmap-footer {
    margin-top: 1.5rem;
    border-top: 1px solid #f3f4f6;
    padding-top: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.heatmap-legend {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.legend-label {
    font-size: 0.7rem;
    color: #6b7280;
    font-weight: 500;
}

.legend-gradient {
    width: 120px;
    height: 8px;
    background: linear-gradient(to right, rgba(79, 70, 229, 0.1), rgba(79, 70, 229, 1));
    border-radius: 4px;
}

.heatmap-hint {
    color: #9ca3af;
}

.text-truncate {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.filter-divider {
    width: 1px;
    height: 1.25rem;
    background: #e5e7eb;
}

.filter-select {
    padding: 0.375rem 2rem 0.375rem 0.75rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
    background-color: white;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    cursor: pointer;
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
    background-position: right 0.5rem center;
    background-repeat: no-repeat;
    background-size: 1.5em 1.5em;
    appearance: none;
}

.date-input {
    height: 36px;
    padding: 0 0.625rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    color: #374151;
    background: white;
    outline: none;
    transition: border-color 0.2s;
    box-sizing: border-box;
}

.date-input:focus {
    border-color: #4f46e5;
}

.filter-separator {
    font-size: 0.75rem;
    color: #9ca3af;
    font-weight: 500;
}

.btn-link {
    font-size: 0.75rem;
    font-weight: 600;
    color: #4f46e5;
    background: none;
    border: none;
    cursor: pointer;
}

.btn-link:hover {
    text-decoration: underline;
}

.animate-in {
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(-10px);
    }

    to {
        opacity: 1;
        transform: translateX(0);
    }
}
</style>
