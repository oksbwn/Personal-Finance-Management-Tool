<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCurrency } from '@/composables/useCurrency'
import Sparkline from '@/components/Sparkline.vue'
import { ChevronDown, ChevronUp, Users } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()
const { formatAmount } = useCurrency()
const loading = ref(true)

// Member Selection
const selectedMember = ref<string | null>(null)
const familyMembers = ref<any[]>([])
const showMemberDropdown = ref(false)
const memberDropdownRef = ref<HTMLElement | null>(null)

const selectedMemberName = computed(() => {
    if (!selectedMember.value) return 'All Members'
    const member = familyMembers.value.find(m => m.id === selectedMember.value)
    return member ? (member.full_name || member.email) : 'All Members'
})

function toggleMemberDropdown() { showMemberDropdown.value = !showMemberDropdown.value }
function selectMember(id: string | null) {
    selectedMember.value = id
    showMemberDropdown.value = false
}

function handleDropdownOutside(event: MouseEvent) {
    if (memberDropdownRef.value && !memberDropdownRef.value.contains(event.target as Node)) {
        showMemberDropdown.value = false
    }
}
onMounted(() => {
    document.addEventListener('click', handleDropdownOutside)
})
import { onUnmounted } from 'vue'
onUnmounted(() => {
    document.removeEventListener('click', handleDropdownOutside)
})

const mfPortfolio = ref({
    invested: 0,
    current: 0,
    pl: 0,
    plPercent: 0,
    xirr: 0,
    trend: [] as number[],
    allocation: { equity: 0, debt: 0, hybrid: 0, other: 0 } as any,
    topPerformer: null as any,
    loading: true
})
const netWorthTrend = ref<number[]>([])
const spendingTrend = ref<number[]>([])
const recurringTransactions = ref<any[]>([])
const metrics = ref({
    breakdown: {
        net_worth: 0,
        bank_balance: 0,
        cash_balance: 0,
        credit_debt: 0,
        investment_value: 0,
        total_credit_limit: 0,
        available_credit: 0,
        overall_credit_utilization: 0
    },
    monthly_spending: 0,
    top_spending_category: null as { name: string, amount: number } | null,
    budget_health: {
        limit: 0,
        spent: 0,
        percentage: 0
    },
    credit_intelligence: [] as any[],
    recent_transactions: [] as any[],
    currency: 'INR'
})

const budgets = ref<any[]>([])
const categories = ref<any[]>([])

const budgetPulse = computed(() => {
    return budgets.value
        .filter(b => b.category !== 'OVERALL')
        .sort((a, b) => b.percentage - a.percentage)
        .slice(0, 3)
})

const netWorth = computed(() => {
    const liquid = (metrics.value.breakdown.bank_balance || 0) + (metrics.value.breakdown.cash_balance || 0)
    const totalInvestments = mfPortfolio.value.current || 0
    const totalDebt = metrics.value.breakdown.credit_debt || 0
    return liquid + totalInvestments - totalDebt
})

const upcomingBills = computed(() => {
    return recurringTransactions.value
        .filter(t => t.status === 'ACTIVE')
        .slice(0, 3)
})

const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 18) return 'Good afternoon'
    return 'Good evening'
}

function formatDate(dateStr: string) {
    const d = new Date(dateStr)
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

// Helper to get category details including color
function getCategoryDetails(name: string) {
    if (!name || name === 'Uncategorized') return { icon: '🏷️', color: '#f3f4f6' }
    const cat = categories.value.find(c => c.name === name)
    return cat ? { icon: cat.icon || '🏷️', color: cat.color || '#3B82F6' } : { icon: '🏷️', color: '#f3f4f6' }
}

async function fetchAllData() {
    // Show skeleton initially
    loading.value = true
    mfPortfolio.value.loading = true

    const userId = selectedMember.value || undefined

    // Hide main skeleton after a brief moment (data will populate progressively)
    setTimeout(() => { loading.value = false }, 300)

    // 1. Metrics - highest priority
    financeApi.getMetrics(undefined, undefined, undefined, userId)
        .then(res => { metrics.value = res.data })
        .catch(e => console.warn("Metrics fetch failed", e))

    // 2. Portfolio
    financeApi.getPortfolio(userId)
        .then(pfRes => {
            if (pfRes && pfRes.data && Array.isArray(pfRes.data)) {
                let invested = 0
                let current = 0
                pfRes.data.forEach((h: any) => {
                    const inv = Number(h.invested_value || h.investedValue || h.invested_amount || 0)
                    const cur = Number(h.current_value || h.currentValue || h.value || 0)
                    invested += inv
                    current += cur
                })
                mfPortfolio.value.invested = invested
                mfPortfolio.value.current = current
                mfPortfolio.value.pl = current - invested
                mfPortfolio.value.plPercent = invested > 0 ? ((current - invested) / invested) * 100 : 0
            }
        })
        .catch(e => console.warn("Portfolio fetch failed", e))

    // 3. Analytics
    financeApi.getAnalytics(userId)
        .then(anRes => {
            if (anRes && anRes.data) {
                mfPortfolio.value.xirr = Number(anRes.data.xirr || 0)
                mfPortfolio.value.allocation = anRes.data.asset_allocation || { equity: 0, debt: 0, hybrid: 0, other: 0 }
                if (anRes.data.top_gainers && anRes.data.top_gainers.length > 0) {
                    const top = anRes.data.top_gainers[0]
                    mfPortfolio.value.topPerformer = {
                        schemeName: top.scheme_name || top.schemeName || top.scheme,
                        plPercent: Number(top.pl_percent || top.plPercent || top.returns || 0)
                    }
                }
                mfPortfolio.value.loading = false
            }
        })
        .catch(e => {
            console.warn("Analytics fetch failed", e)
            mfPortfolio.value.loading = false
        })

    // 4. Timeline
    financeApi.getPerformanceTimeline('1m', '1d', userId)
        .then(timelineRes => {
            if (timelineRes && timelineRes.data && (Array.isArray(timelineRes.data.timeline) || Array.isArray(timelineRes.data))) {
                const timelineArr = Array.isArray(timelineRes.data) ? timelineRes.data : timelineRes.data.timeline
                mfPortfolio.value.trend = timelineArr.map((p: any) => Number(p.value || 0))
            }
        })
        .catch(e => console.warn("Timeline fetch failed", e))

    // 5. Recurring
    financeApi.getRecurringTransactions()
        .then(recurringRes => { recurringTransactions.value = recurringRes.data })
        .catch(e => console.warn("Recurring fetch failed", e))

    // 6. Net Worth Trend
    financeApi.getNetWorthTimeline(30, userId)
        .then(nwRes => {
            if (nwRes && nwRes.data) {
                netWorthTrend.value = nwRes.data.map((p: any) => Number(p.total || 0))
            }
        })
        .catch(e => console.warn("Net worth trend failed", e))

    // 7. Spending Trend
    financeApi.getSpendingTrend(userId)
        .then(spendRes => {
            if (spendRes && spendRes.data) {
                spendingTrend.value = spendRes.data.map((p: any) => Number(p.amount || 0))
            }
        })
        .catch(e => console.warn("Spending trend failed", e))
}

onMounted(async () => {
    // Fetch common data (once)
    try {
        const [usersRes, catRes, budgetRes] = await Promise.all([
            financeApi.getUsers(),
            financeApi.getCategories(),
            financeApi.getBudgets()
        ])
        familyMembers.value = usersRes.data
        categories.value = catRes.data
        budgets.value = budgetRes.data
    } catch (e) {
        console.error("Failed to fetch initial dashboard metadata", e)
    }

    await fetchAllData()
})

watch(selectedMember, () => {
    fetchAllData()
})
</script>

<template>
    <MainLayout>
        <div class="dashboard-container">
            <!-- Header -->
            <div class="dashboard-header">
                <div class="header-left">
                    <span class="greeting-pre">{{ getGreeting() }},</span>
                    <h1 class="user-name">Welcome Back</h1>
                </div>

                <div class="header-right-actions">
                    <!-- Custom Member Filter -->
                    <div class="member-selector-container" v-if="auth.user?.role !== 'CHILD'" ref="memberDropdownRef">
                        <button class="member-selector-trigger" @click.stop="toggleMemberDropdown">
                            <Users :size="16" class="mr-2" />
                            <span class="selected-label">{{ selectedMemberName }}</span>
                            <component :is="showMemberDropdown ? ChevronUp : ChevronDown" :size="16" class="ml-2" />
                        </button>

                        <transition name="fade-slide">
                            <div v-if="showMemberDropdown" class="premium-dropdown">
                                <div class="dropdown-item" :class="{ 'active': selectedMember === null }"
                                    @click="selectMember(null)">
                                    <Users :size="14" class="mr-2" /> All Members
                                </div>
                                <div class="dropdown-divider"></div>
                                <div v-for="user in familyMembers" :key="user.id" class="dropdown-item"
                                    :class="{ 'active': selectedMember === user.id }" @click="selectMember(user.id)">
                                    <span class="avatar-mini">{{ user.full_name?.charAt(0) || user.email.charAt(0)
                                        }}</span>
                                    <div class="member-info">
                                        <div class="name">{{ user.full_name || user.email.split('@')[0] }}</div>
                                        <div class="role">{{ user.role }}</div>
                                    </div>
                                </div>
                            </div>
                        </transition>
                    </div>

                    <div class="date-badge">
                        {{ new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
                        }}
                    </div>
                </div>
            </div>


            <div v-if="loading" class="dashboard-grid skeleton-grid">
                <!-- Skeleton Metric Cards -->
                <div class="skeleton-card" v-for="i in 4" :key="`metric-${i}`">
                    <div class="skeleton-header">
                        <div class="skeleton-circle"></div>
                        <div class="skeleton-text skeleton-text-sm"></div>
                    </div>
                    <div class="skeleton-text skeleton-text-lg"></div>
                    <div class="skeleton-text skeleton-text-xs"></div>
                </div>

                <!-- Skeleton Chart Cards -->
                <div class="skeleton-card skeleton-card-wide" v-for="i in 2" :key="`chart-${i}`">
                    <div class="skeleton-text skeleton-text-md"></div>
                    <div class="skeleton-chart"></div>
                </div>

                <!-- Skeleton Budget Cards -->
                <div class="skeleton-card" v-for="i in 3" :key="`budget-${i}`">
                    <div class="skeleton-text skeleton-text-sm"></div>
                    <div class="skeleton-bar"></div>
                    <div class="skeleton-text skeleton-text-xs"></div>
                </div>
            </div>

            <div v-else class="dashboard-grid animate-in">
                <!-- ROW 1: Key Metrics (Net Worth, Spending, Budget, Credit) -->
                <div class="metric-card net-worth-card h-glow-primary">
                    <div class="card-icon-bg purple">🏦</div>
                    <div class="card-data">
                        <span class="label">Balance Sheet Net Worth</span>
                        <span class="value">{{ formatAmount(netWorth) }}</span>
                        <!-- Sparkline -->
                        <div v-if="netWorthTrend.length > 1" class="card-sparkline" style="margin-top: 8px;">
                            <Sparkline :data="netWorthTrend" color="#8b5cf6" :height="20" />
                        </div>
                    </div>
                </div>

                <div class="metric-card spending-card h-glow-danger">
                    <div class="card-icon-bg red">💸</div>
                    <div class="card-data">
                        <span class="label">Monthly Spending</span>
                        <span class="value">{{ formatAmount(metrics.monthly_spending, metrics.currency) }}</span>

                        <div v-if="metrics.top_spending_category" class="sub-text"
                            style="font-size: 0.7rem; color: var(--color-text-muted); margin-top: 4px;">
                            Top: <span style="font-weight: 600; color: var(--color-text-main);">{{
                                metrics.top_spending_category.name }}</span>
                        </div>

                        <!-- Sparkline -->
                        <div v-if="spendingTrend.length > 1" class="card-sparkline" style="margin-top: 8px;">
                            <Sparkline :data="spendingTrend" color="#ef4444" :height="20" />
                        </div>
                    </div>
                </div>

                <div class="metric-card budget-card h-glow-warning"
                    :class="{ 'pulse-critical': metrics.budget_health.percentage > 100 }"
                    @click="router.push('/budgets')">
                    <div class="card-top-row">
                        <div class="card-icon-bg orange">📊</div>
                        <span class="mini-percent" :class="{ 'danger': metrics.budget_health.percentage > 100 }">
                            {{ metrics.budget_health.percentage.toFixed(0) }}%
                        </span>
                    </div>
                    <div class="card-data">
                        <span class="label">Budget Target</span>
                        <div class="progress-bar-xs">
                            <div class="fill" :style="{ width: Math.min(metrics.budget_health.percentage, 100) + '%' }"
                                :class="{ 'danger': metrics.budget_health.percentage > 90 }"></div>
                        </div>
                        <span class="sub-text">
                            {{ metrics.budget_health.spent > metrics.budget_health.limit ? 'Overspent by ' : '' }}
                            {{ formatAmount(Math.abs(metrics.budget_health.limit - metrics.budget_health.spent),
                                metrics.currency) }}
                            {{ metrics.budget_health.spent > metrics.budget_health.limit ? '' : 'left' }}
                        </span>
                    </div>
                </div>

                <!-- Investment Pulse Card (New) -->
                <div class="metric-card investment-card h-glow-green" @click="router.push('/mutual-funds')"
                    style="grid-column: span 1;">
                    <div class="card-top-row">
                        <div class="card-icon-bg green">🚀</div>
                        <span v-if="!mfPortfolio.loading && mfPortfolio.invested > 0" class="mini-percent"
                            :class="mfPortfolio.xirr >= 0 ? 'success' : 'danger'">
                            {{ mfPortfolio.xirr.toFixed(1) }}% XIRR
                        </span>
                    </div>
                    <div class="card-data">
                        <span class="label">Investments</span>
                        <div v-if="mfPortfolio.loading">
                            <div style="height: 24px; background: #f3f4f6; border-radius: 4px; width: 60%; margin-bottom: 4px;"
                                class="pulse"></div>
                        </div>
                        <div v-else>
                            <span class="value">{{ formatAmount(mfPortfolio.current) }}</span>
                            <div style="font-size: 0.75rem; font-weight: 600; margin-top: 0.25rem;"
                                :class="mfPortfolio.pl >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                                {{ mfPortfolio.pl >= 0 ? '+' : '' }}{{ formatAmount(mfPortfolio.pl) }} ({{
                                    mfPortfolio.plPercent.toFixed(1) }}%)
                            </div>

                            <!-- Asset Allocation Mini Bar -->
                            <div v-if="mfPortfolio.current > 0" class="mini-allocation-bar">
                                <div v-if="mfPortfolio.allocation.equity > 0" class="allocation-segment equity"
                                    :style="{ width: mfPortfolio.allocation.equity + '%' }" title="Equity"></div>
                                <div v-if="mfPortfolio.allocation.debt > 0" class="allocation-segment debt"
                                    :style="{ width: mfPortfolio.allocation.debt + '%' }" title="Debt"></div>
                                <div v-if="mfPortfolio.allocation.hybrid > 0" class="allocation-segment hybrid"
                                    :style="{ width: mfPortfolio.allocation.hybrid + '%' }" title="Hybrid"></div>
                                <div v-if="!(mfPortfolio.allocation.equity || mfPortfolio.allocation.debt || mfPortfolio.allocation.hybrid)"
                                    class="allocation-segment"
                                    style="width: 100%; background: #e2e8f0; border-radius: 3px;"
                                    title="No allocation data"></div>
                            </div>

                            <!-- Trend -->
                            <div v-if="mfPortfolio.trend.length > 1" class="card-sparkline">
                                <Sparkline :data="mfPortfolio.trend"
                                    :color="mfPortfolio.pl >= 0 ? '#10b981' : '#ef4444'" :height="24" />
                            </div>
                            <div v-else class="sub-text" style="font-size: 0.6rem; opacity: 0.5; margin: 4px 0;">
                                Trend: {{ mfPortfolio.trend.length > 0 ? 'Insufficient data' : 'No data' }}
                            </div>

                            <!-- Top Performer Info -->
                            <div v-if="mfPortfolio.topPerformer" class="tp-info animate-in">
                                <span class="tp-label">Top: {{ mfPortfolio.topPerformer.schemeName }}</span>
                                <span class="tp-val success">+{{ mfPortfolio.topPerformer.plPercent }}%</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ROW 2: Budget Pulse (Surfacing category limits) -->
                <div v-if="budgetPulse.length > 0" class="dashboard-section pulse-section glass-panel">
                    <div class="section-header">
                        <div class="header-with-badge">
                            <h3>Budget Pulse</h3>
                            <span class="pulse-status-badge">Live Monitor</span>
                        </div>
                        <button class="btn-text" @click="router.push('/budgets')">Manage Limits</button>
                    </div>
                    <div class="pulse-grid">
                        <div v-for="b in budgetPulse" :key="b.id" class="pulse-card" @click="router.push('/budgets')">
                            <div class="pulse-card-top">
                                <span class="pulse-cat">{{ getCategoryDetails(b.category).icon }} {{ b.category
                                    }}</span>
                                <span class="pulse-percent" :class="{ 'danger': b.percentage > 100 }">{{
                                    b.percentage.toFixed(0) }}%</span>
                            </div>
                            <div class="pulse-bar-bg">
                                <div class="pulse-bar-fill"
                                    :style="{ width: Math.min(b.percentage, 100) + '%', backgroundColor: b.percentage > 100 ? '#ef4444' : (b.percentage > 85 ? '#f59e0b' : '#6366f1') }">
                                </div>
                            </div>
                            <div class="pulse-footer">
                                {{ formatAmount(b.spent, metrics.currency) }} of {{ formatAmount(b.amount_limit,
                                    metrics.currency) }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ROW 3: Account Snapshot & Recent Activity -->

                <!-- Snapshot -->
                <div class="dashboard-section snapshot-section glass-panel">
                    <div class="section-header">
                        <h3>Liquidity Snapshot</h3>
                    </div>
                    <div class="snapshot-grid">
                        <div class="snapshot-item">
                            <span class="snap-icon">🏛️</span>
                            <div class="snap-info">
                                <span class="snap-label">Bank Accounts</span>
                                <span class="snap-val">{{ formatAmount(metrics.breakdown.bank_balance, metrics.currency)
                                    }}</span>
                            </div>
                        </div>
                        <div class="snapshot-item">
                            <span class="snap-icon">👛</span>
                            <div class="snap-info">
                                <span class="snap-label">Cash / Wallet</span>
                                <span class="snap-val">{{ formatAmount(metrics.breakdown.cash_balance, metrics.currency)
                                    }}</span>
                            </div>
                        </div>
                        <div class="snapshot-item" @click="router.push('/mutual-funds')" style="cursor: pointer;">
                            <span class="snap-icon">📈</span>
                            <div class="snap-info">
                                <span class="snap-label">Investments</span>
                                <span class="snap-val" :class="{ 'text-emerald-600': mfPortfolio.current > 0 }">
                                    {{ formatAmount(mfPortfolio.current) }}
                                </span>
                            </div>
                        </div>
                        <div class="snapshot-item" @click="router.push('/settings')" style="cursor: pointer;">
                            <span class="snap-icon">💳</span>
                            <div class="snap-info">
                                <span class="snap-label">Avail. Credit</span>
                                <span class="snap-val">{{ formatAmount(metrics.breakdown.available_credit,
                                    metrics.currency) }}</span>
                                <span v-if="metrics.breakdown.overall_credit_utilization > 0" class="snap-util" :class="{
                                    'util-low': metrics.breakdown.overall_credit_utilization < 30,
                                    'util-medium': metrics.breakdown.overall_credit_utilization >= 30 && metrics.breakdown.overall_credit_utilization < 70,
                                    'util-high': metrics.breakdown.overall_credit_utilization >= 70
                                }">
                                    {{ metrics.breakdown.overall_credit_utilization.toFixed(1) }}% used
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Upcoming Bills Subsection -->
                    <div class="upcoming-bills-section">
                        <div class="sub-section-header">
                            <h4>Upcoming Bills</h4>
                        </div>
                        <div v-if="upcomingBills.length > 0" class="upcoming-list">
                            <div v-for="bill in upcomingBills" :key="bill.id" class="bill-row">
                                <div class="bill-left">
                                    <span class="bill-icon">{{ getCategoryDetails(bill.category).icon }}</span>
                                    <div class="bill-info">
                                        <span class="bill-name">{{ bill.description }}</span>
                                        <span class="bill-date">Due on {{ formatDate(bill.next_date) }}</span>
                                    </div>
                                </div>
                                <div class="bill-amount">{{ formatAmount(bill.amount) }}</div>
                            </div>
                        </div>
                        <div v-else class="empty-state-diag">
                            No active recurring bills found.
                        </div>
                    </div>
                </div>

                <!-- Recent Activity -->
                <div class="dashboard-section activity-section glass-panel">
                    <div class="section-header">
                        <h3>Recent Activity</h3>
                        <button class="btn-text" @click="router.push('/transactions')">View All</button>
                    </div>
                    <div v-if="metrics.recent_transactions.length === 0" class="empty-state-sm">
                        No recent transactions
                    </div>
                    <div v-else class="recent-list">
                        <div v-for="txn in metrics.recent_transactions" :key="txn.id" class="recent-item">
                            <div class="recent-left">
                                <div class="cat-circle"
                                    :style="{ backgroundColor: getCategoryDetails(txn.category).color + '20', color: getCategoryDetails(txn.category).color }">
                                    {{ getCategoryDetails(txn.category).icon }}
                                </div>
                                <div class="recent-meta">
                                    <span class="recent-desc">{{ txn.description || 'Unknown' }}</span>
                                    <div class="recent-date-row">
                                        <span class="recent-date">{{ formatDate(txn.date) }}</span>
                                        <span v-if="txn.account_owner_name" class="owner-badge">
                                            {{ txn.account_owner_name }}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <span class="recent-amount" :class="{ 'credit': txn.amount > 0 }">
                                {{ txn.amount > 0 ? '+' : '' }}{{ formatAmount(Math.abs(txn.amount), metrics.currency)
                                }}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Credit Intelligence -->
                <div class="dashboard-section credit-intel-section glass-panel">
                    <div class="section-header">
                        <div class="header-with-badge">
                            <h3>Credit Intelligence</h3>
                            <span class="pulse-status-badge" style="background: #eef2ff; color: #4f46e5;">Cycles</span>
                        </div>
                    </div>
                    <div v-if="metrics.credit_intelligence.length > 0" class="credit-list">
                        <div v-for="card in metrics.credit_intelligence" :key="card.id" class="card-intel-item">
                            <div class="card-intel-top">
                                <span class="card-intel-name">💳 {{ card.name }}</span>
                                <span v-if="card.days_until_due !== null" class="card-intel-status"
                                    :class="{ 'danger': card.days_until_due < 5, 'warning': card.days_until_due < 10 }">
                                    {{ card.days_until_due }} days left
                                </span>
                                <span v-else class="card-intel-status muted">No due date</span>
                            </div>
                            <div class="card-intel-util">
                                <div class="util-bar-bg">
                                    <div class="util-bar-fill"
                                        :style="{ width: Math.min(card.utilization, 100) + '%', backgroundColor: card.utilization > 50 ? '#f59e0b' : '#6366f1' }">
                                    </div>
                                </div>
                                <span class="util-text">{{ card.utilization.toFixed(0) }}% Limit Used</span>
                            </div>
                            <div class="card-intel-footer">
                                <div class="intel-stat">
                                    <span class="stat-label">Billing Day</span>
                                    <span class="stat-value">{{ card.billing_day || '—' }}</span>
                                </div>
                                <div class="intel-stat">
                                    <span class="stat-label">Due Day</span>
                                    <span class="stat-value">{{ card.due_day || '—' }}</span>
                                </div>
                                <div class="intel-stat" style="text-align: right;">
                                    <span class="stat-label">Balance</span>
                                    <span class="stat-value">{{ formatAmount(card.balance) }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else class="empty-state-diag">
                        No credit accounts with limits configured.
                    </div>
                </div>

            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
.dashboard-container {
    width: 100%;
    margin: 0 auto;
    padding-bottom: 3rem;
}

.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
}

.header-right-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.header-left {
    display: flex;
    flex-direction: column;
}

.greeting-pre {
    font-size: 0.9rem;
    color: var(--color-text-muted);
    font-weight: 500;
    margin-bottom: 0.25rem;
}

.user-name {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--color-text-main);
    margin: 0;
    line-height: 1.1;
}

.date-badge {
    background: white;
    padding: 0.5rem 1rem;
    border-radius: 2rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    box-shadow: var(--shadow-sm);
}

.member-selector-container {
    position: relative;
}

.member-selector-trigger {
    display: flex;
    align-items: center;
    background: white;
    border: 1px solid var(--color-border);
    padding: 0.5rem 1rem;
    border-radius: 2rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-main);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-sm);
}

.member-selector-trigger:hover {
    border-color: var(--color-primary);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}

.premium-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 0.75rem;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(10px);
    border: 1px solid var(--color-border);
    border-radius: 1rem;
    box-shadow: var(--shadow-lg);
    width: 240px;
    padding: 0.5rem;
    z-index: 200;
}

.dropdown-item {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.9rem;
    color: var(--color-text-main);
}

.dropdown-item:hover {
    background: var(--color-background);
    color: var(--color-primary);
}

.dropdown-item.active {
    background: var(--color-primary-light);
    color: var(--color-primary);
    font-weight: 600;
}

.dropdown-divider {
    height: 1px;
    background: var(--color-border);
    margin: 0.5rem;
}

.avatar-mini {
    width: 24px;
    height: 24px;
    background: var(--color-primary-light);
    color: var(--color-primary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 700;
    margin-right: 0.75rem;
    text-transform: uppercase;
}

.member-info {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
}

.member-info .name {
    font-weight: 600;
    font-size: 0.85rem;
}

.member-info .role {
    font-size: 0.7rem;
    color: var(--color-text-muted);
    text-transform: capitalize;
}

/* Transitions */
.fade-slide-enter-active,
.fade-slide-leave-active {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from,
.fade-slide-leave-to {
    opacity: 0;
    transform: translateY(-10px);
}


/* Skeleton Loading */
.skeleton-grid {
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }

    to {
        opacity: 1;
    }
}

.skeleton-card {
    background: white;
    border-radius: 1.25rem;
    padding: 1.5rem;
    border: 1px solid var(--color-border);
    overflow: hidden;
    position: relative;
}

.skeleton-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg,
            transparent 0%,
            rgba(255, 255, 255, 0.6) 50%,
            transparent 100%);
    animation: shimmer 2s infinite;
}

@keyframes shimmer {
    0% {
        left: -100%;
    }

    100% {
        left: 100%;
    }
}

.skeleton-card-wide {
    grid-column: span 2;
}

.skeleton-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.skeleton-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--color-background);
}

.skeleton-text {
    background: var(--color-background);
    border-radius: 0.5rem;
    height: 12px;
    margin-bottom: 0.75rem;
}

.skeleton-text-xs {
    width: 40%;
    height: 10px;
}

.skeleton-text-sm {
    width: 60%;
    height: 12px;
}

.skeleton-text-md {
    width: 50%;
    height: 16px;
    margin-bottom: 1.5rem;
}

.skeleton-text-lg {
    width: 70%;
    height: 24px;
    margin-bottom: 0.5rem;
}

.skeleton-chart {
    width: 100%;
    height: 180px;
    background: var(--color-background);
    border-radius: 0.75rem;
    position: relative;
    overflow: hidden;
}

.skeleton-bar {
    width: 100%;
    height: 8px;
    background: var(--color-background);
    border-radius: 1rem;
    margin: 0.75rem 0;
}

/* Old loader (kept for compatibility) */
.loading-state {
    padding: 4rem;
    text-align: center;
    color: var(--color-text-muted);
}

.spinner {
    width: 30px;
    height: 30px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #4f46e5;
    border-radius: 50%;
    margin: 0 auto 1rem;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}

/* Grid Layout */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
}

.animate-in {
    animation: slideUp 0.4s ease-out forwards;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Sync Monitor */
.sync-monitor-banner {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    padding: 0.5rem;
    background: #f8fafc;
    border: 1px dashed #e2e8f0;
    border-radius: 12px;
}

.sync-pill {
    font-size: 0.7rem;
    font-weight: 700;
    color: #64748b;
    padding: 0.25rem 0.6rem;
    background: white;
    border-radius: 20px;
    border: 1px solid #f1f5f9;
}

/* Metric Cards */
.metric-card {
    background: white;
    border-radius: 1.25rem;
    padding: 1.25rem;
    border: 1px solid var(--color-border);
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    overflow: hidden;
    cursor: default;
}

/* Hover Glows */
.h-glow-primary:hover {
    box-shadow: 0 8px 20px rgba(79, 70, 229, 0.15);
    border-color: #a5b4fc;
}

.h-glow-danger:hover {
    box-shadow: 0 8px 20px rgba(239, 68, 68, 0.15);
    border-color: #fca5a5;
}

.h-glow-warning:hover {
    box-shadow: 0 8px 20px rgba(245, 158, 11, 0.15);
    border-color: #fcd34d;
    cursor: pointer;
}

.h-glow-blue:hover {
    box-shadow: 0 8px 20px rgba(59, 130, 246, 0.15);
    border-color: #93c5fd;
    cursor: pointer;
}

.h-glow-green:hover {
    box-shadow: 0 8px 20px rgba(16, 185, 129, 0.15);
    border-color: #6ee7b7;
    cursor: pointer;
}

.card-icon-bg {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    margin-bottom: 0.75rem;
}

.purple {
    background: #eef2ff;
    color: #4f46e5;
}

.red {
    background: #fef2f2;
    color: #ef4444;
}

.orange {
    background: #fffbeb;
    color: #f59e0b;
}

.blue {
    background: #eff6ff;
    color: #3b82f6;
}

.green {
    background: #ecfdf5;
    color: #10b981;
}

.indigo {
    background: #e0e7ff;
    color: #6366f1;
}

.card-data {
    display: flex;
    flex-direction: column;
}

.label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}

.value {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--color-text-main);
    letter-spacing: -0.025em;
}

/* Complex Cards */
.card-top-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.75rem;
}

.card-top-row .card-icon-bg {
    margin-bottom: 0;
}

.mini-percent {
    font-size: 0.8rem;
    font-weight: 700;
    color: #374151;
    background: #f3f4f6;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
}

.mini-percent.danger {
    color: #dc2626;
    background: #fef2f2;
}

.mini-percent.success {
    color: #059669;
    background: #ecfdf5;
}

.progress-bar-xs {
    height: 6px;
    background: #f3f4f6;
    border-radius: 3px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}

.progress-bar-xs .fill {
    height: 100%;
    background: #f59e0b;
    border-radius: 3px;
}

.progress-bar-xs .fill.blue {
    background: #3b82f6;
}

.sub-text {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-weight: 500;
}

/* Investment Specifics */
.card-sparkline {
    margin-top: 0.75rem;
    margin-bottom: 0.5rem;
    height: 24px;
}

.tp-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px dashed #e2e8f0;
    margin-top: 0.5rem;
}

.tp-label {
    font-size: 0.65rem;
    color: var(--color-text-muted);
    font-weight: 600;
    max-width: 70%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tp-val {
    font-size: 0.7rem;
    font-weight: 800;
}

.tp-val.success {
    color: #10b981;
}

.empty-state-diag {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-style: italic;
    padding: 0.5rem;
    background: #f8fafc;
    border-radius: 6px;
    text-align: center;
}

/* Asset Allocation Bar */
.mini-allocation-bar {
    display: flex;
    height: 6px;
    border-radius: 3px;
    background: #f1f5f9;
    overflow: hidden;
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
}

.allocation-segment {
    height: 100%;
}

.allocation-segment.equity {
    background: #6366f1;
}

.allocation-segment.debt {
    background: #10b981;
}

.allocation-segment.hybrid {
    background: #f59e0b;
}

/* Upcoming Bills */
.upcoming-bills-section {
    margin-top: 1.5rem;
    padding-top: 1.25rem;
    border-top: 1px solid #f1f5f9;
}

.sub-section-header h4 {
    font-size: 0.8rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}

.upcoming-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.bill-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    border-radius: 8px;
    background: rgba(248, 250, 252, 0.5);
    transition: background 0.2s;
}

.bill-row:hover {
    background: #f1f5f9;
}

.bill-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.bill-icon {
    font-size: 1.25rem;
    padding: 0.4rem;
    background: white;
    border-radius: 6px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.bill-info {
    display: flex;
    flex-direction: column;
}

.bill-name {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-dark);
}

.bill-date {
    font-size: 0.7rem;
    color: var(--color-text-muted);
}

.bill-amount {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--color-text-dark);
}

/* Sections */
.dashboard-section {
    background: white;
    border-radius: 1.25rem;
    border: 1px solid var(--color-border);
    padding: 1.5rem;
}

.snapshot-section {
    grid-column: span 2;
}

.activity-section {
    grid-column: span 2;
}

.pulse-section {
    grid-column: span 4;
}

.credit-intel-section {
    grid-column: span 4;
}

.header-with-badge {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.pulse-status-badge {
    padding: 0.25rem 0.5rem;
    background: #e0e7ff;
    color: #4338ca;
    font-size: 0.65rem;
    font-weight: 800;
    border-radius: 4px;
    text-transform: uppercase;
}

.glass-panel {
    background: rgba(255, 255, 255, 0.8);
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.25rem;
}

.section-header h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-main);
}

.btn-text {
    background: none;
    border: none;
    font-size: 0.8rem;
    font-weight: 600;
    color: #4f46e5;
    cursor: pointer;
}

.btn-text:hover {
    text-decoration: underline;
}

/* Snapshot Grid */
.snapshot-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.snapshot-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    border-radius: 0.75rem;
    background: #f9fafb;
    transition: all 0.2s;
}

.snapshot-item:hover {
    background: #f3f4f6;
}

.snap-icon {
    font-size: 1.25rem;
}

.snap-info {
    display: flex;
    flex-direction: column;
}

.snap-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
}

.snap-val {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-main);
}

.snap-util {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    display: inline-block;
    margin-top: 0.25rem;
    width: fit-content;
}

.util-low {
    background: #dcfce7;
    color: #166534;
}

.util-medium {
    background: #ffedd5;
    color: #9a3412;
}

.util-high {
    background: #fee2e2;
    color: #991b1b;
}

/* Recent Activity */
.recent-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.recent-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f3f4f6;
}

.recent-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.recent-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.cat-circle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #f3f4f6;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}

.recent-meta {
    display: flex;
    flex-direction: column;
}

.recent-desc {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--color-text-main);
}

.recent-date-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.recent-date {
    font-size: 0.7rem;
    color: var(--color-text-muted);
}

.owner-badge {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--color-primary);
    background: var(--color-primary-light);
    padding: 0.125rem 0.5rem;
    border-radius: 1rem;
    text-transform: capitalize;
}

.recent-amount {
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--color-text-main);
}

.recent-amount.credit {
    color: #10b981;
}

.empty-state-sm {
    text-align: center;
    color: var(--color-text-muted);
    font-size: 0.85rem;
    padding: 2rem 0;
}

/* Pulse Grid */
.pulse-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
}

.pulse-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.875rem;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.2s;
}

.pulse-card:hover {
    border-color: #cbd5e1;
    transform: scale(1.02);
}

.pulse-card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.pulse-cat {
    font-size: 0.8125rem;
    font-weight: 700;
    color: #374151;
}

.pulse-percent {
    font-size: 0.8125rem;
    font-weight: 800;
    color: #6366f1;
}

.pulse-percent.danger {
    color: #ef4444;
}

.pulse-bar-bg {
    height: 4px;
    background: #e5e7eb;
    border-radius: 2px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}

.pulse-bar-fill {
    height: 100%;
    transition: width 1s ease-out;
}

.pulse-footer {
    font-size: 0.7rem;
    color: #64748b;
    font-weight: 500;
}

.pulse-critical {
    animation: criticalPulse 2s infinite;
    border-color: #fecaca !important;
}

@keyframes criticalPulse {
    0% {
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
    }

    70% {
        box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
    }

    100% {
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
    }
}

/* Credit Intelligence List */
.credit-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
}

.card-intel-item {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.875rem;
    padding: 1rem;
}

.card-intel-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}

.card-intel-name {
    font-weight: 700;
    font-size: 0.9rem;
    color: #1e293b;
}

.card-intel-status {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.125rem 0.5rem;
    border-radius: 1rem;
    background: #f1f5f9;
    color: #475569;
}

.card-intel-status.warning {
    background: #fff7ed;
    color: #ea580c;
}

.card-intel-status.danger {
    background: #fef2f2;
    color: #dc2626;
}

.card-intel-util {
    margin-bottom: 0.75rem;
}

.util-bar-bg {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    margin-bottom: 0.25rem;
    overflow: hidden;
}

.util-bar-fill {
    height: 100%;
    transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
}

.util-text {
    font-size: 0.65rem;
    font-weight: 600;
    color: #64748b;
}

.card-intel-footer {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    border-top: 1px dashed #e2e8f0;
    padding-top: 0.75rem;
    margin-top: 0.25rem;
}

.intel-stat {
    display: flex;
    flex-direction: column;
}

.stat-label {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.025em;
    color: #94a3b8;
    font-weight: 700;
}

.stat-value {
    font-size: 0.8rem;
    font-weight: 700;
    color: #334155;
}

/* Mobile Responsive */
@media (max-width: 1024px) {
    .dashboard-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .pulse-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 640px) {
    .dashboard-grid {
        grid-template-columns: 1fr;
    }

    .snapshot-section,
    .activity-section {
        grid-column: span 1;
    }
}
</style>
