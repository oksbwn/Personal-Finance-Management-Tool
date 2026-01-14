<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import { useCurrency } from '@/composables/useCurrency'

const { formatAmount } = useCurrency()
const notify = useNotificationStore()

const budgets = ref<any[]>([])
const categories = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('list')

const showModal = ref(false)
const newBudget = ref({
    category: '',
    amount_limit: null as number | null
})

// Metrics
const overallBudget = computed(() => budgets.value.find(b => b.category === 'OVERALL'))
const categoryBudgets = computed(() => budgets.value.filter(b => b.category !== 'OVERALL'))

// For Summary Cards (exclude OVERALL from sum to avoid double counting if we just want sum of categories?)
// OR do we want sum of categories?
// Current logic: Sum of ALL budgets. If OVERALL exists, it might be confusing to sum it with others.
// Let's change Summary Cards to: "Total Budget (Sum of Categories)" vs "Overall Limit".
// actually if OVERALL exists, that IS the limit.
// Let's refine summary:
// If OVERALL exists: Show "Overall Limit", "Total Spent", "Remaining".
// If NOT: Show "Sum of Category Budgets", etc.
const effectiveTotalBudget = computed(() => {
    if (overallBudget.value) return Number(overallBudget.value.amount_limit)
    return categoryBudgets.value.reduce((sum, b) => sum + Number(b.amount_limit), 0)
})
const totalSpent = computed(() => {
    if (overallBudget.value) return Number(overallBudget.value.spent)
     return categoryBudgets.value.reduce((sum, b) => sum + Number(b.spent), 0)
})
const totalRemaining = computed(() => effectiveTotalBudget.value - totalSpent.value)

const categoryOptions = computed(() => {
    return categories.value.map(c => ({
        label: `${c.icon || '🏷️'} ${c.name}`,
        value: c.name
    }))
})

function getCategoryDisplay(name: string) {
    if (name === 'OVERALL') return '🏁 Overall Monthly Limit'
    if (!name) return '📝 General'
    const cat = categories.value.find(c => c.name === name)
    return cat ? `${cat.icon || '🏷️'} ${cat.name}` : `🏷️ ${name}`
}

async function fetchData() {
    loading.value = true
    try {
        const [budgetRes, catRes] = await Promise.all([
            financeApi.getBudgets(),
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
    if(!confirm("Remove this budget?")) return
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
            <div class="page-header-compact">
                <div class="header-left">
                    <h1 class="page-title">Budgets</h1>
                    <div class="header-tabs">
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'list' }" 
                            @click="activeTab = 'list'"
                        >
                            List
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'analytics' }" 
                            @click="activeTab = 'analytics'"
                        >
                            Analytics
                        </button>
                    </div>
                </div>
                
                <div class="header-actions">
                    <button v-if="!overallBudget" class="btn-outline-compact" @click="openSetBudgetModal(true)">
                        + Total Limit
                    </button>
                    <button class="btn-primary-glow" @click="openSetBudgetModal(false)">
                        <span class="btn-icon-plus">+</span> Set Category
                    </button>
                </div>
            </div>

            <div v-if="loading" class="loading-state">
                <div class="loader-spinner"></div>
                <p>Calculating your spending power...</p>
            </div>

            <div v-else>
                <!-- LIST VIEW -->
                <div v-if="activeTab === 'list'" class="tab-content animate-in">
                    <!-- Overall Budget Hero Card -->
                    <div v-if="overallBudget" class="overall-glass-card">
                        <div class="card-top">
                            <div class="card-main">
                                <span class="card-label">Overall Monthly Limit</span>
                                <div class="price-row">
                                    <span class="amount-large">{{ formatAmount(overallBudget.spent) }}</span>
                                    <span class="separator">/</span>
                                    <span class="total-limit">{{ formatAmount(overallBudget.amount_limit) }}</span>
                                </div>
                            </div>
                            <div class="card-actions">
                                <button @click="editBudget(overallBudget)" class="btn-icon-circle">✏️</button>
                                <button @click="deleteBudget(overallBudget.id)" class="btn-icon-circle danger">🗑️</button>
                            </div>
                        </div>

                        <div class="progress-container-lg">
                            <div class="progress-bar-bg-lg">
                                <div class="progress-bar-fill-lg" 
                                    :style="{ width: Math.min(overallBudget.percentage, 100) + '%' }"
                                    :class="{ 
                                        'warning': overallBudget.percentage > 80 && overallBudget.percentage <= 100,
                                        'danger': overallBudget.percentage > 100 
                                    }"
                                ></div>
                            </div>
                            <div class="progress-meta">
                                <span class="percentage-badge" :class="{ 'over': overallBudget.percentage > 100 }">
                                    {{ overallBudget.percentage?.toFixed(1) }}% Used
                                </span>
                                <span class="remaining-text" :class="{ 'over': overallBudget.remaining < 0 }">
                                    {{ overallBudget.remaining >= 0 ? `${formatAmount(overallBudget.remaining)} remaining` : `${formatAmount(Math.abs(overallBudget.remaining))} overspent` }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Summary Grid -->
                    <div class="summary-widgets-budget">
                        <div class="mini-stat-card glass h-glow-primary">
                            <div class="stat-top">
                                <span class="stat-label">Budgeted</span>
                                <span class="stat-icon-bg gray">📑</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(effectiveTotalBudget) }}</div>
                        </div>
                        <div class="mini-stat-card glass h-glow-danger">
                            <div class="stat-top">
                                <span class="stat-label">Total Outflow</span>
                                <span class="stat-icon-bg red">💸</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(totalSpent) }}</div>
                        </div>
                        <div class="mini-stat-card glass h-glow-success">
                            <div class="stat-top">
                                <span class="stat-label">Budget Safe</span>
                                <span class="stat-icon-bg green">🛡️</span>
                            </div>
                            <div class="stat-value" :class="{ 'negative': totalRemaining < 0 }">{{ formatAmount(totalRemaining) }}</div>
                        </div>
                    </div>

                    <h2 class="section-title">Category Limits</h2>
                    <div class="budget-grid">
                        <div v-for="b in categoryBudgets" :key="b.id" class="glass-card budget-card">
                            <div class="card-top">
                                <div class="card-main">
                                    <span class="card-name">{{ getCategoryDisplay(b.category) }}</span>
                                </div>
                                <div class="card-actions">
                                    <button @click="editBudget(b)" class="btn-icon-circle-sm">✏️</button>
                                    <button @click="deleteBudget(b.id)" class="btn-icon-circle-sm danger">🗑️</button>
                                </div>
                            </div>
                            
                            <div class="progress-section">
                                <div class="progress-info-compact">
                                    <span class="spent">{{ formatAmount(b.spent) }}</span>
                                    <span class="limit">of {{ formatAmount(b.amount_limit) }}</span>
                                </div>
                                <div class="progress-bar-bg-sm">
                                    <div class="progress-bar-fill-sm" 
                                        :style="{ width: Math.min(b.percentage, 100) + '%' }"
                                        :class="{ 
                                            'warning': b.percentage > 80 && b.percentage <= 100,
                                            'danger': b.percentage > 100 
                                        }"
                                    ></div>
                                </div>
                                <div class="remaining-footer" :class="{ 'over': b.remaining < 0 }">
                                    {{ b.remaining >= 0 ? `${formatAmount(b.remaining)} left` : `${formatAmount(Math.abs(b.remaining))} over` }}
                                </div>
                            </div>
                        </div>

                        <div v-if="categoryBudgets.length === 0" class="empty-card" @click="openSetBudgetModal(false)">
                            <span class="empty-plus">+</span>
                            <p>Enforce category limit</p>
                        </div>
                    </div>
                </div>

                <!-- ANALYTICS VIEW -->
                <div v-else-if="activeTab === 'analytics'" class="tab-content animate-in">
                    <div class="analytics-grid-budget">
                        <!-- Utilization Gauge (Mockup for now, could use SVG like transactions) -->
                        <div class="analytics-card glass">
                            <div class="card-header">
                                <h3 class="card-title">Budget Health</h3>
                            </div>
                            <div class="gauge-container">
                                <svg viewBox="0 0 100 60" class="gauge-svg">
                                    <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#f3f4f6" stroke-width="8" stroke-linecap="round" />
                                    <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" 
                                          :stroke="overallBudget?.percentage > 100 ? '#ef4444' : (overallBudget?.percentage > 80 ? '#f59e0b' : '#10b981')" 
                                          stroke-width="8" stroke-linecap="round"
                                          :stroke-dasharray="125" :stroke-dashoffset="125 - (125 * Math.min(overallBudget?.percentage || 0, 100) / 100)" />
                                </svg>
                                <div class="gauge-value">
                                    <span class="val">{{ overallBudget?.percentage?.toFixed(0) || 0 }}%</span>
                                    <span class="lbl">Utilized</span>
                                </div>
                            </div>
                        </div>

                        <!-- Top Burners -->
                        <div class="analytics-card glass">
                            <div class="card-header">
                                <h3 class="card-title">Critical Categories</h3>
                            </div>
                            <div class="burner-list">
                                <div v-for="b in [...categoryBudgets].sort((x,y) => y.percentage - x.percentage).slice(0,4)" :key="b.id" class="burner-item">
                                    <div class="burner-info">
                                        <span class="burner-label">{{ getCategoryDisplay(b.category) }}</span>
                                        <span class="burner-val" :class="{ 'danger': b.percentage > 100 }">{{ b.percentage?.toFixed(0) }}%</span>
                                    </div>
                                    <div class="burner-bar-bg">
                                        <div class="burner-bar-fill" :style="{ width: Math.min(b.percentage, 100) + '%' }" :class="{ 'danger': b.percentage > 100 }"></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Budget vs Reality Chart (Mockup SVG) -->
                        <div class="analytics-card glass full-width">
                            <div class="card-header">
                                <h3 class="card-title">Monthly Budget Adherence</h3>
                            </div>
                            <div class="budget-chart">
                                <div v-for="b in categoryBudgets" :key="b.id" class="chart-col">
                                    <div class="bar-pair">
                                        <div class="bar limit-bar" :title="'Limit: ' + b.amount_limit" :style="{ height: '100px' }"></div>
                                        <div class="bar spend-bar" :title="'Spent: ' + b.spent" :class="{ 'over': b.spent > b.amount_limit }" :style="{ height: Math.min(100 * b.spent / b.amount_limit, 150) + 'px' }"></div>
                                    </div>
                                    <span class="col-label">{{ b.category }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Budget Modal -->
        <div v-if="showModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ newBudget.category === 'OVERALL' ? 'Total Monthly Limit' : 'Category Budget' }}</h2>
                    <button class="btn-icon-circle" @click="showModal = false">✕</button>
                </div>

                <form @submit.prevent="saveBudget" class="form-compact">
                    <div class="form-group" v-if="newBudget.category !== 'OVERALL'">
                        <label class="form-label">Category</label>
                        <CustomSelect 
                            v-model="newBudget.category"
                            :options="categoryOptions"
                            placeholder="Select Category"
                        />
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Monthly Limit (₹)</label>
                        <div class="amount-input-wrapper">
                            <span class="input-prefix">₹</span>
                            <input type="number" v-model="newBudget.amount_limit" class="form-input" required placeholder="5,000" />
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
.page-header-compact {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.25rem;
    gap: 1.5rem;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.page-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    margin: 0;
    letter-spacing: -0.025em;
}

.header-tabs {
    display: flex;
    gap: 0.125rem;
    background: #f3f4f6;
    padding: 0.125rem;
    border-radius: 0.625rem;
}

.tab-btn {
    padding: 0.375rem 1rem;
    border: none;
    background: transparent;
    border-radius: 0.5rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn.active {
    background: white;
    color: #111827;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.header-actions {
    display: flex;
    gap: 0.75rem;
}

.btn-primary-glow {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
    color: white;
    border: none;
    border-radius: 0.625rem;
    font-size: 0.8125rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 4px 10px rgba(79, 70, 229, 0.15);
}

.btn-outline-compact {
    padding: 0.5rem 1rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.625rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #4b5563;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-outline-compact:hover {
    background: #f9fafb;
    border-color: #d1d5db;
}

/* Overall Hero Card */
.overall-glass-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 1.25rem;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.03);
}

.price-row {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
    margin-top: 0.25rem;
}

.currency { font-size: 1.25rem; font-weight: 600; color: #6b7280; }
.amount-large { font-size: 2.25rem; font-weight: 800; color: #111827; letter-spacing: -0.05em; }
.separator { font-size: 1.5rem; color: #d1d5db; margin: 0 0.5rem; }
.total-limit { font-size: 1.25rem; font-weight: 600; color: #6b7280; }

.progress-container-lg {
    margin-top: 1.5rem;
}

.progress-bar-bg-lg {
    height: 12px;
    background: #f3f4f6;
    border-radius: 6px;
    overflow: hidden;
}

.progress-bar-fill-lg {
    height: 100%;
    background: #10b981;
    transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.progress-bar-fill-lg.warning { background: #f59e0b; }
.progress-bar-fill-lg.danger { background: #ef4444; }

.progress-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.75rem;
}

.percentage-badge {
    padding: 0.25rem 0.625rem;
    background: #ecfdf5;
    color: #059669;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
}

.percentage-badge.over { background: #fef2f2; color: #dc2626; }

.remaining-text {
    font-size: 0.875rem;
    font-weight: 600;
    color: #6b7280;
}

.remaining-text.over { color: #dc2626; }

/* Summary Widgets */
.summary-widgets-budget {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.875rem;
    margin-bottom: 2rem;
}

/* Category Grid */
.budget-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.875rem;
}

.glass-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 1rem;
    padding: 1rem;
    transition: all 0.2s;
}

.budget-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}

.progress-info-compact {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
    margin-top: 0.75rem;
}

.spent { font-size: 1rem; font-weight: 700; color: #111827; }
.limit { font-size: 0.75rem; color: #9ca3af; }

.progress-bar-bg-sm {
    height: 6px;
    background: #f3f4f6;
    border-radius: 3px;
    margin: 0.5rem 0;
    overflow: hidden;
}

.progress-bar-fill-sm {
    height: 100%;
    background: #10b981;
}
.progress-bar-fill-sm.warning { background: #f59e0b; }
.progress-bar-fill-sm.danger { background: #ef4444; }

.remaining-footer {
    font-size: 0.7rem;
    font-weight: 600;
    color: #6b7280;
    text-align: right;
}

.remaining-footer.over { color: #dc2626; }

/* Analytics View */
.analytics-grid-budget {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
}

.analytics-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 1rem;
    padding: 1.25rem;
}

.full-width { grid-column: 1 / -1; }

.card-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #374151;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}

/* Gauge Mockup */
.gauge-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    padding-top: 1rem;
}

.gauge-svg {
    width: 200px;
    height: 120px;
}

.gauge-value {
    position: absolute;
    bottom: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.gauge-value .val { font-size: 1.5rem; font-weight: 800; color: #111827; }
.gauge-value .lbl { font-size: 0.7rem; color: #9ca3af; text-transform: uppercase; font-weight: 600; }

/* Burner List */
.burner-list { display: flex; flex-direction: column; gap: 0.75rem; }
.burner-info { display: flex; justify-content: space-between; margin-bottom: 0.25rem; }
.burner-label { font-size: 0.8125rem; font-weight: 600; color: #4b5563; }
.burner-val { font-size: 0.8125rem; font-weight: 700; color: #10b981; }
.burner-val.danger { color: #ef4444; }

.burner-bar-bg { height: 4px; background: #f3f4f6; border-radius: 2px; overflow: hidden; }
.burner-bar-fill { height: 100%; background: #10b981; }
.burner-bar-fill.danger { background: #ef4444; }

/* Budget Chart Mockup */
.budget-chart {
    display: flex;
    align-items: flex-end;
    gap: 1.5rem;
    height: 200px;
    padding: 1rem;
    overflow-x: auto;
}

.chart-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    min-width: 60px;
}

.bar-pair {
    position: relative;
    width: 24px;
    height: 150px;
    display: flex;
    align-items: flex-end;
}

.bar { width: 100%; border-radius: 4px 4px 0 0; }
.limit-bar { background: #f3f4f6; position: absolute; bottom: 0; left: 0; z-index: 1; opacity: 0.5; }
.spend-bar { background: #10b981; position: absolute; bottom: 0; left: 0; z-index: 2; }
.spend-bar.over { background: #ef4444; }

.col-label { font-size: 0.65rem; font-weight: 600; color: #9ca3af; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60px; }

/* States & Global Reused */
.loading-state { padding: 4rem 0; text-align: center; color: #6b7280; }
.loader-spinner { width: 32px; height: 32px; border: 3px solid #f3f3f3; border-top: 3px solid #4f46e5; border-radius: 50%; margin: 0 auto 1rem; animation: spin 1s linear infinite; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

.animate-in { animation: slideUp 0.4s ease-out forwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

/* Shared Stat Cards */
.mini-stat-card { background: white; border: 1px solid #e5e7eb; border-radius: 0.875rem; padding: 0.875rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; transition: all 0.2s; }
.mini-stat-card:hover { transform: translateY(-2px); border-color: #d1d5db; }
.stat-top { display: flex; justify-content: space-between; align-items: center; }
.stat-label { font-size: 0.7rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-icon-bg { width: 32px; height: 32px; border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; font-size: 1rem; }
.stat-icon-bg.gray { background: #f3f4f6; }
.stat-icon-bg.red { background: #fef2f2; }
.stat-icon-bg.green { background: #ecfdf5; }
.stat-value { font-size: 1.25rem; font-weight: 800; color: #111827; letter-spacing: -0.025em; }
.stat-value.negative { color: #dc2626; }

.btn-icon-circle { width: 2.25rem; height: 2.25rem; border-radius: 50%; border: none; background: #f9fafb; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; }
.btn-icon-circle:hover { background: #f3f4f6; }
.btn-icon-circle.danger:hover { background: #fef2f2; color: #dc2626; }
.btn-icon-circle-sm { width: 1.75rem; height: 1.75rem; border-radius: 50%; border: none; background: #f9fafb; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; font-size: 0.75rem; }
.btn-icon-circle-sm:hover { background: #f3f4f6; }

.section-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin: 1.5rem 0 0.875rem; color: #6b7280; }

.empty-card { border: 2px dashed #e5e7eb; border-radius: 1rem; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; cursor: pointer; transition: all 0.2s; color: #9ca3af; }
.empty-card:hover { border-color: #4f46e5; background: #f5f3ff; color: #4f46e5; }
.empty-plus { font-size: 1.5rem; font-weight: 300; margin-bottom: 0.5rem; }

/* Modal Enhancement */
.form-compact .form-group { margin-bottom: 1rem; }
.amount-input-wrapper { position: relative; }
.input-prefix { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); font-weight: 600; color: #6b7280; }
.amount-input-wrapper .form-input { padding-left: 2rem; }
.btn-secondary { padding: 0.625rem 1.25rem; background: white; border: 1px solid #e5e7eb; border-radius: 0.75rem; font-weight: 600; cursor: pointer; }

/* Glow Effects */
.h-glow-primary:hover { box-shadow: 0 4px 15px rgba(79, 70, 229, 0.1); }
.h-glow-success:hover { box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1); }
.h-glow-danger:hover { box-shadow: 0 4px 15px rgba(239, 68, 68, 0.1); }
</style>
