<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import { useRouter } from 'vue-router'
import { useCurrency } from '@/composables/useCurrency'

const router = useRouter()
const { formatAmount } = useCurrency()
const loading = ref(true)
const metrics = ref({
    breakdown: {
        net_worth: 0,
        bank_balance: 0,
        cash_balance: 0,
        credit_debt: 0,
        investment_value: 0,
        total_credit_limit: 0,
        available_credit: 0
    },
    monthly_spending: 0,
    budget_health: {
        limit: 0,
        spent: 0,
        percentage: 0
    },
    recent_transactions: [] as any[],
    currency: 'INR'
})

// Computed
const creditUtilPercent = computed(() => {
    const limit = metrics.value.breakdown.total_credit_limit
    const debt = metrics.value.breakdown.credit_debt
    if (!limit || limit === 0) return 0
    return Math.min((debt / limit) * 100, 100)
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

    const categories = ref<any[]>([])

    // Helper to get category details including color
    function getCategoryDetails(name: string) {
        if (!name || name === 'Uncategorized') return { icon: '🏷️', color: '#f3f4f6' }
        const cat = categories.value.find(c => c.name === name)
        return cat ? { icon: cat.icon || '🏷️', color: cat.color || '#3B82F6' } : { icon: '🏷️', color: '#f3f4f6' }
    }

    onMounted(async () => {
        try {
            const [res, catRes] = await Promise.all([
                financeApi.getMetrics(),
                financeApi.getCategories()
            ])
            metrics.value = res.data
            categories.value = catRes.data
        } catch (e) {
            console.error("Failed to load metrics", e)
        } finally {
            loading.value = false
        }
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
            <div class="date-badge">
                {{ new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }) }}
            </div>
        </div>

        <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <p>Gathering financial intelligence...</p>
        </div>

        <div v-else class="dashboard-grid animate-in">
            
            <!-- ROW 1: Key Metrics (Net Worth, Spending, Budget, Credit) -->
            <div class="metric-card net-worth-card h-glow-primary">
                <div class="card-icon-bg purple">🏦</div>
                <div class="card-data">
                    <span class="label">Net Worth</span>
                    <span class="value">{{ formatAmount(metrics.breakdown.net_worth, metrics.currency) }}</span>
                </div>
            </div>

            <div class="metric-card spending-card h-glow-danger">
                <div class="card-icon-bg red">💸</div>
                <div class="card-data">
                    <span class="label">Monthly Spending</span>
                    <span class="value">{{ formatAmount(metrics.monthly_spending, metrics.currency) }}</span>
                </div>
            </div>

            <div class="metric-card budget-card h-glow-warning" @click="router.push('/budgets')">
                <div class="card-top-row">
                    <div class="card-icon-bg orange">📊</div>
                    <span class="mini-percent" :class="{'danger': metrics.budget_health.percentage > 100}">
                        {{ metrics.budget_health.percentage.toFixed(0) }}%
                    </span>
                </div>
                <div class="card-data">
                    <span class="label">Budget Used</span>
                    <div class="progress-bar-xs">
                        <div class="fill" :style="{ width: Math.min(metrics.budget_health.percentage, 100) + '%' }"></div>
                    </div>
                    <span class="sub-text">
                        {{ formatAmount(metrics.budget_health.limit - metrics.budget_health.spent, metrics.currency) }} left
                    </span>
                </div>
            </div>

            <div class="metric-card credit-card h-glow-blue" @click="router.push('/settings')">
                <div class="card-top-row">
                    <div class="card-icon-bg blue">💳</div>
                    <span class="mini-percent">{{ creditUtilPercent.toFixed(0) }}%</span>
                </div>
                <div class="card-data">
                    <span class="label">Credit Utilization</span>
                    <div class="progress-bar-xs">
                        <div class="fill blue" :style="{ width: creditUtilPercent + '%' }"></div>
                    </div>
                    <span class="sub-text">
                        {{ formatAmount(metrics.breakdown.available_credit, metrics.currency) }} available
                    </span>
                </div>
            </div>

            <!-- ROW 2: Account Snapshot & Recent Activity -->
            
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
                            <span class="snap-val">{{ formatAmount(metrics.breakdown.bank_balance, metrics.currency) }}</span>
                        </div>
                    </div>
                    <div class="snapshot-item">
                        <span class="snap-icon">👛</span>
                        <div class="snap-info">
                            <span class="snap-label">Cash / Wallet</span>
                            <span class="snap-val">{{ formatAmount(metrics.breakdown.cash_balance, metrics.currency) }}</span>
                        </div>
                    </div>
                    <div class="snapshot-item">
                        <span class="snap-icon">📈</span>
                        <div class="snap-info">
                            <span class="snap-label">Investments</span>
                            <span class="snap-val">{{ formatAmount(metrics.breakdown.investment_value, metrics.currency) }}</span>
                        </div>
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
                            <div class="cat-circle" :style="{ backgroundColor: getCategoryDetails(txn.category).color + '20', color: getCategoryDetails(txn.category).color }">
                                {{ getCategoryDetails(txn.category).icon }}
                            </div>
                            <div class="recent-meta">
                                <span class="recent-desc">{{ txn.description || 'Unknown' }}</span>
                                <span class="recent-date">{{ formatDate(txn.date) }}</span>
                            </div>
                        </div>
                        <span class="recent-amount" :class="{ 'credit': txn.amount > 0 }">
                            {{ txn.amount > 0 ? '+' : '' }}{{ formatAmount(Math.abs(txn.amount), metrics.currency) }}
                        </span>
                    </div>
                </div>
            </div>

        </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.dashboard-container {
    max-width: 1200px;
    margin: 0 auto;
    padding-bottom: 3rem;
}

.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 2rem;
}

.header-left { display: flex; flex-direction: column; }
.greeting-pre { font-size: 0.9rem; color: var(--color-text-muted); font-weight: 500; margin-bottom: 0.25rem; }
.user-name { font-size: 1.75rem; font-weight: 800; color: var(--color-text-main); margin: 0; line-height: 1.1; }

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

/* Loader */
.loading-state { padding: 4rem; text-align: center; color: var(--color-text-muted); }
.spinner { width: 30px; height: 30px; border: 3px solid #f3f3f3; border-top: 3px solid #4f46e5; border-radius: 50%; margin: 0 auto 1rem; animation: spin 1s linear infinite; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

/* Grid Layout */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
}

.animate-in { animation: slideUp 0.4s ease-out forwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

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
.h-glow-primary:hover { box-shadow: 0 8px 20px rgba(79, 70, 229, 0.15); border-color: #a5b4fc; }
.h-glow-danger:hover { box-shadow: 0 8px 20px rgba(239, 68, 68, 0.15); border-color: #fca5a5; }
.h-glow-warning:hover { box-shadow: 0 8px 20px rgba(245, 158, 11, 0.15); border-color: #fcd34d; cursor: pointer; }
.h-glow-blue:hover { box-shadow: 0 8px 20px rgba(59, 130, 246, 0.15); border-color: #93c5fd; cursor: pointer; }

.card-icon-bg {
    width: 40px; height: 40px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem;
    margin-bottom: 0.75rem;
}

.purple { background: #eef2ff; color: #4f46e5; }
.red { background: #fef2f2; color: #ef4444; }
.orange { background: #fffbeb; color: #f59e0b; }
.blue { background: #eff6ff; color: #3b82f6; }

.card-data { display: flex; flex-direction: column; }
.label { font-size: 0.75rem; color: var(--color-text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
.value { font-size: 1.5rem; font-weight: 800; color: var(--color-text-main); letter-spacing: -0.025em; }

/* Complex Cards */
.card-top-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; }
.card-top-row .card-icon-bg { margin-bottom: 0; }
.mini-percent { font-size: 0.8rem; font-weight: 700; color: #374151; background: #f3f4f6; padding: 0.1rem 0.4rem; border-radius: 4px; }
.mini-percent.danger { color: #dc2626; background: #fef2f2; }

.progress-bar-xs {
    height: 6px;
    background: #f3f4f6;
    border-radius: 3px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}
.progress-bar-xs .fill { height: 100%; background: #f59e0b; border-radius: 3px; }
.progress-bar-xs .fill.blue { background: #3b82f6; }

.sub-text { font-size: 0.75rem; color: var(--color-text-muted); font-weight: 500; }

/* Sections */
.dashboard-section {
    background: white;
    border-radius: 1.25rem;
    border: 1px solid var(--color-border);
    padding: 1.5rem;
}

.snapshot-section { grid-column: span 2; }
.activity-section { grid-column: span 2; }

.glass-panel {
    background: rgba(255, 255, 255, 0.8);
}

.section-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1.25rem;
}
.section-header h3 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-main); }
.btn-text { background: none; border: none; font-size: 0.8rem; font-weight: 600; color: #4f46e5; cursor: pointer; }
.btn-text:hover { text-decoration: underline; }

/* Snapshot Grid */
.snapshot-grid { display: flex; flex-direction: column; gap: 1rem; }
.snapshot-item { 
    display: flex; align-items: center; gap: 1rem; 
    padding: 0.75rem; border-radius: 0.75rem;
    background: #f9fafb; transition: all 0.2s;
}
.snapshot-item:hover { background: #f3f4f6; }
.snap-icon { font-size: 1.25rem; }
.snap-info { display: flex; flex-direction: column; }
.snap-label { font-size: 0.75rem; font-weight: 600; color: var(--color-text-muted); }
.snap-val { font-size: 1rem; font-weight: 700; color: var(--color-text-main); }

/* Recent Activity */
.recent-list { display: flex; flex-direction: column; gap: 0.75rem; }
.recent-item { 
    display: flex; justify-content: space-between; align-items: center; 
    padding-bottom: 0.75rem; border-bottom: 1px solid #f3f4f6;
}
.recent-item:last-child { border-bottom: none; padding-bottom: 0; }

.recent-left { display: flex; align-items: center; gap: 0.75rem; }
.cat-circle { 
    width: 32px; height: 32px; border-radius: 50%; background: #f3f4f6; 
    display: flex; align-items: center; justify-content: center; font-size: 1rem; 
}

.recent-meta { display: flex; flex-direction: column; }
.recent-desc { font-weight: 600; font-size: 0.9rem; color: var(--color-text-main); }
.recent-date { font-size: 0.7rem; color: var(--color-text-muted); }

.recent-amount { font-weight: 700; font-size: 0.9rem; color: var(--color-text-main); }
.recent-amount.credit { color: #10b981; }

.empty-state-sm { text-align: center; color: var(--color-text-muted); font-size: 0.85rem; padding: 2rem 0; }

/* Mobile Responsive */
@media (max-width: 1024px) {
    .dashboard-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
    .dashboard-grid { grid-template-columns: 1fr; }
    .snapshot-section, .activity-section { grid-column: span 1; }
}
</style>
