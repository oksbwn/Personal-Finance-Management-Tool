<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useFinanceStore } from '@/stores/finance'
import { financeApi } from '@/api/client'
import { useCurrency } from '@/composables/useCurrency'

const store = useFinanceStore()
const { formatAmount } = useCurrency()

const activeTab = ref<'analytics' | 'recurring'>('analytics')

// Data for Analytics
const transactions = ref<any[]>([])
const loading = ref(false)

onMounted(async () => {
    await store.fetchAll()
    fetchAnalyticsData()
})

async function fetchAnalyticsData() {
    loading.value = true
    try {
        // Fetch last 1000 transactions for analytics
        // In a real app, this should probably be a dedicated metrics API
        const res = await financeApi.getTransactions(undefined, 1, 1000)
        transactions.value = res.data.items
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

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
    const catMap: Record<string, number> = {}
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
        const absAmt = Math.abs(amt)

        if (isTransfer) return

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
        return Object.entries(map).sort((a,b) => b[1] - a[1]).map(([name, value]) => ({ name, value }))
    }

    return {
        income,
        expense,
        net: income - expense,
        categories: Object.entries(catMap).sort((a,b) => b[1] - a[1]).map(([name, value]) => ({
            name, value, color: store.getCategoryColor(name), icon: store.getCategoryIcon(name)
        })),
        merchants: toSortedArray(merchantMap).slice(0, 5),
        accounts: toSortedArray(accountMap),
        types: toSortedArray(typeMap),
        trends: Object.entries(dateMap).sort((a,b) => a[0].localeCompare(b[0])).slice(-14).map(([date, value]) => ({ date, value })),
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

// --- Recurring Logic ---
const showAddModal = ref(false)
const processing = ref(false)

const newRecurrence = ref({
    name: '',
    amount: 0,
    category: '',
    account_id: '',
    frequency: 'MONTHLY',
    start_date: new Date().toISOString().slice(0, 10),
    type: 'DEBIT' 
})

async function triggerProcess() {
    processing.value = true
    try {
        await financeApi.processRecurring()
        await store.fetchRecurring()
    } catch (e) {
        console.error(e)
    } finally {
        processing.value = false
    }
}

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
    if(!confirm("Stop this subscription?")) return;
    financeApi.deleteRecurring(id).then(() => store.fetchRecurring())
}

const frequencyOptions = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']

</script>

<template>
    <MainLayout>
        <div class="p-6 space-y-6">
            <!-- Header -->
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 class="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
                        Insights & Subscriptions
                    </h1>
                    <p class="text-gray-500 text-sm mt-1">Analyze spending patterns and manage recurring bills</p>
                </div>
                
                <div class="flex bg-white rounded-lg p-1 shadow-sm border border-gray-200">
                    <button 
                        @click="activeTab = 'analytics'"
                        :class="['px-4 py-2 text-sm font-medium rounded-md transition-all', 
                        activeTab === 'analytics' ? 'bg-indigo-50 text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-900']"
                    >
                        Analytics
                    </button>
                    <button 
                        @click="activeTab = 'recurring'"
                        :class="['px-4 py-2 text-sm font-medium rounded-md transition-all', 
                        activeTab === 'recurring' ? 'bg-indigo-50 text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-900']"
                    >
                        Recurring
                    </button>
                </div>
            </div>

            <!-- ANALYTICS TAB -->
            <div v-if="activeTab === 'analytics'" class="animate-fade-in space-y-6">
                <!-- AI Insight Card -->
                <div class="glass-card p-6 bg-gradient-to-br from-indigo-50 to-purple-50 border-indigo-100 relative overflow-hidden">
                    <div class="flex justify-between items-center mb-4 relative z-10">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-sm text-xl animate-bounce-slow">
                                ✨
                            </div>
                            <div>
                                <h3 class="font-semibold text-gray-900">AI Spending Analysis</h3>
                                <p class="text-xs text-gray-500">Based on your recent activity</p>
                            </div>
                        </div>
                        <button class="btn-secondary text-xs flex items-center gap-2 hover:bg-white hover:shadow-sm">
                            <span>🤖</span> Generate Insights
                        </button>
                    </div>
                    <p class="text-sm text-gray-600 leading-relaxed relative z-10">
                        Use the "Generate Insights" button to get a personalized analysis of your spending habits, anomaly detection, and budget recommendations powered by Gemini.
                    </p>
                    <!-- Decorative background blobs -->
                    <div class="absolute top-0 right-0 w-32 h-32 bg-purple-200/20 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
                    <div class="absolute bottom-0 left-0 w-24 h-24 bg-indigo-200/20 rounded-full translate-y-1/2 -translate-x-1/2 blur-2xl"></div>
                </div>

                <!-- Summary Cards -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <!-- ... existing summary cards ... -->
                    <div class="glass-card p-4 flex items-center gap-4">
                        <div class="p-3 bg-green-50 text-green-600 rounded-full text-xl">⚡</div>
                        <div>
                            <p class="text-xs text-gray-500 font-medium">Total Income</p>
                            <p class="text-xl font-bold text-gray-900">{{ formatAmount(analyticsData.income) }}</p>
                        </div>
                    </div>
                    <div class="glass-card p-4 flex items-center gap-4">
                        <div class="p-3 bg-red-50 text-red-600 rounded-full text-xl">🔥</div>
                        <div>
                            <p class="text-xs text-gray-500 font-medium">Total Expenses</p>
                            <p class="text-xl font-bold text-gray-900">{{ formatAmount(analyticsData.expense) }}</p>
                        </div>
                    </div>
                    <div class="glass-card p-4 flex items-center gap-4">
                        <div class="p-3 bg-blue-50 text-blue-600 rounded-full text-xl">💰</div>
                        <div>
                            <p class="text-xs text-gray-500 font-medium">Net Savings</p>
                            <p class="text-xl font-bold text-gray-900" :class="analyticsData.net < 0 ? 'text-red-600' : 'text-green-600'">
                                {{ formatAmount(analyticsData.net) }}
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Forecast Chart -->
                <div class="glass-card p-6">
                    <h3 class="font-semibold text-gray-800 mb-4">Future Balance Forecast (30 Days)</h3>
                    <div class="h-64 flex items-end justify-between gap-1 border-b border-gray-100 pb-4 relative">
                        <!-- Simple visual approximation of a line chart using bars for now, typically would use Chart.js -->
                         <div class="absolute inset-0 flex items-center justify-center text-gray-400 text-sm bg-gray-50/50 rounded-lg border border-dashed border-gray-200">
                            <div class="text-center">
                                <span class="text-2xl block mb-2">📈</span>
                                Forecasting requires more historical data.<br>
                                <span class="text-xs opacity-75">Visual forecast will appear here once Chart.js is integrated.</span>
                            </div>
                        </div>
                    </div>
                     <div class="flex justify-between mt-4 text-sm text-gray-500">
                        <span>Based on recurring transactions & average spending</span>
                        <span>Projected: {{ formatAmount(analyticsData.net + (store.recurringTransactions.reduce((acc, t) => acc + (t.type === 'DEBIT' ? -t.amount : t.amount), 0))) }}</span>
                    </div>
                </div>

                <!-- Main Analytics Grid -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Category Breakdown -->
                    <div class="glass-card p-6">
                        <h3 class="font-semibold text-gray-800 mb-4">Category Breakdown</h3>
                        <div class="space-y-4">
                            <div v-for="cat in analyticsData.categories.slice(0, 6)" :key="cat.name" class="space-y-1">
                                <div class="flex justify-between text-sm">
                                    <span class="flex items-center gap-2">
                                        <span>{{ cat.icon }}</span> {{ cat.name }}
                                    </span>
                                    <span class="font-medium">{{ formatAmount(cat.value) }}</span>
                                </div>
                                <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                                    <div class="h-full rounded-full transition-all duration-500" 
                                        :style="{ width: `${(cat.value / analyticsData.expense * 100)}%`, backgroundColor: cat.color }">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Trends -->
                    <div class="glass-card p-6">
                        <h3 class="font-semibold text-gray-800 mb-4">Daily Spending Trend</h3>
                        <div class="h-48 flex items-end gap-2">
                            <div v-for="day in analyticsData.trends" :key="day.date" 
                                class="flex-1 bg-indigo-100 rounded-t-sm hover:bg-indigo-200 transition-colors relative group"
                                :style="{ height: `${(day.value / Math.max(...analyticsData.trends.map(d => d.value), 1) * 100)}%` }">
                                <div class="opacity-0 group-hover:opacity-100 absolute bottom-full mb-1 left-1/2 -translate-x-1/2 text-xs bg-gray-800 text-white px-2 py-1 rounded whitespace-nowrap z-10">
                                    {{ day.date.slice(5) }}: {{ formatAmount(day.value) }}
                                </div>
                            </div>
                        </div>
                        <div class="flex justify-between mt-2 text-xs text-gray-400">
                            <span>14 days ago</span>
                            <span>Today</span>
                        </div>
                    </div>

                    <!-- Top Merchants -->
                    <div class="glass-card p-6">
                        <h3 class="font-semibold text-gray-800 mb-4">Top Merchants</h3>
                        <div class="space-y-3">
                            <div v-for="(m, i) in analyticsData.merchants" :key="m.name" class="flex justify-between items-center p-2 hover:bg-gray-50 rounded-lg">
                                <div class="flex items-center gap-3">
                                    <span class="w-6 h-6 flex items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-500">{{ i + 1 }}</span>
                                    <span class="text-sm font-medium text-gray-700">{{ m.name }}</span>
                                </div>
                                <span class="text-sm font-bold text-gray-900">{{ formatAmount(m.value) }}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Insights & Patterns -->
                    <div class="glass-card p-6 space-y-6">
                         <!-- Credit Utilization -->
                         <div v-if="analyticsData.credit.limit > 0">
                            <h4 class="text-sm font-medium text-gray-500 mb-2">Credit Utilization</h4>
                            <div class="flex justify-between text-xs mb-1">
                                <span>Used: {{ formatAmount(analyticsData.credit.consumed) }}</span>
                                <span>Limit: {{ formatAmount(analyticsData.credit.limit) }}</span>
                            </div>
                            <div class="h-3 bg-gray-100 rounded-full overflow-hidden">
                                <div class="h-full transition-all duration-500"
                                    :class="analyticsData.credit.percent > 80 ? 'bg-red-500' : (analyticsData.credit.percent > 50 ? 'bg-yellow-500' : 'bg-green-500')"
                                    :style="{ width: `${analyticsData.credit.percent}%` }">
                                </div>
                            </div>
                        </div>

                         <!-- Weekend vs Weekday -->
                         <div>
                            <h4 class="text-sm font-medium text-gray-500 mb-2">Spending Habits</h4>
                            <div class="flex gap-4">
                                <div class="flex-1">
                                    <div class="flex justify-between text-xs mb-1">
                                        <span>Weekdays</span>
                                        <span>{{ analyticsData.patterns.weekdayPercent.toFixed(0) }}%</span>
                                    </div>
                                    <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                                        <div class="h-full bg-blue-500" :style="{ width: `${analyticsData.patterns.weekdayPercent}%` }"></div>
                                    </div>
                                </div>
                                <div class="flex-1">
                                    <div class="flex justify-between text-xs mb-1">
                                        <span>Weekends</span>
                                        <span>{{ analyticsData.patterns.weekendPercent.toFixed(0) }}%</span>
                                    </div>
                                    <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                                        <div class="h-full bg-purple-500" :style="{ width: `${analyticsData.patterns.weekendPercent}%` }"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- RECURRING TAB -->
            <div v-else class="animate-fade-in space-y-6">
                <div class="flex justify-between items-center">
                    <h2 class="text-lg font-semibold text-gray-800">Active Subscriptions</h2>
                    <div class="flex gap-2">
                        <button @click="triggerProcess" :disabled="processing" class="btn-secondary text-sm">
                            <span v-if="processing">Processing...</span>
                            <span v-else>⚡ Run Checks Now</span>
                        </button>
                         <button @click="showAddModal = true" class="btn-primary text-sm">
                            + Add Recurring
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-for="rec in store.recurringTransactions" :key="rec.id" 
                        class="glass-card p-4 hover:shadow-md transition-all relative overflow-hidden group">
                        
                        <div class="flex justify-between items-start mb-2">
                            <div class="flex items-center gap-3">
                                <span class="text-2xl p-2 bg-gray-50 rounded-lg">{{ store.getCategoryIcon(rec.category) }}</span>
                                <div>
                                    <h3 class="font-medium text-gray-900">{{ rec.name }}</h3>
                                    <p class="text-xs text-gray-500 capitalize">{{ rec.frequency.toLowerCase() }} • {{ store.getAccountName(rec.account_id) }}</p>
                                </div>
                            </div>
                            <span class="font-bold text-gray-900">{{ formatAmount(rec.amount) }}</span>
                        </div>

                        <div class="mt-3 flex justify-between items-center text-xs text-gray-400">
                             <span>Next: {{ new Date(rec.next_run_date).toLocaleDateString() }}</span>
                             <button @click="deleteRecurrence(rec.id)" class="text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity">Stop</button>
                        </div>
                        
                        <!-- Progress bar for next due? -->
                         <div class="absolute bottom-0 left-0 h-1 bg-indigo-500 opacity-10 w-full"></div>
                    </div>

                    <!-- Empty State -->
                    <div v-if="store.recurringTransactions.length === 0" class="col-span-full py-12 text-center text-gray-400">
                        No recurring transactions set up.
                    </div>
                </div>
            </div>
        </div>

        <!-- Add Modal -->
        <div v-if="showAddModal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-scale-up">
                <div class="p-6 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                    <h3 class="font-semibold text-lg text-gray-800">New Subscription</h3>
                    <button @click="showAddModal = false" class="text-gray-400 hover:text-gray-600">✕</button>
                </div>
                
                <div class="p-6 space-y-4">
                    <div>
                        <label class="block text-xs font-medium text-gray-500 mb-1">Name</label>
                        <input v-model="newRecurrence.name" type="text" placeholder="e.g. Netflix" class="input-field w-full" autofocus>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-500 mb-1">Amount</label>
                            <input v-model="newRecurrence.amount" type="number" class="input-field w-full">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-gray-500 mb-1">Frequency</label>
                            <select v-model="newRecurrence.frequency" class="input-field w-full">
                                <option v-for="f in frequencyOptions" :key="f" :value="f">{{ f }}</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
                            <input v-model="newRecurrence.start_date" type="date" class="input-field w-full">
                        </div>
                         <div>
                            <label class="block text-xs font-medium text-gray-500 mb-1">Account</label>
                            <select v-model="newRecurrence.account_id" class="input-field w-full">
                                <option v-for="a in store.accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
                            </select>
                        </div>
                    </div>
                    
                     <div>
                        <label class="block text-xs font-medium text-gray-500 mb-1">Category</label>
                        <select v-model="newRecurrence.category" class="input-field w-full">
                             <option v-for="c in store.categories" :key="c.id" :value="c.name">{{ c.icon }} {{ c.name }}</option>
                        </select>
                    </div>

                </div>
                
                <div class="p-6 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
                    <button @click="showAddModal = false" class="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors">Cancel</button>
                    <button @click="saveRecurrence" class="btn-primary">Start Subscription</button>
                </div>
            </div>
        </div>

    </MainLayout>
</template>

<style scoped>
.glass-card {
    @apply bg-white/80 backdrop-blur-md rounded-xl border border-white/20 shadow-sm transition-all duration-300;
}
.btn-primary {
    @apply bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200;
}
.btn-secondary {
    @apply bg-white text-gray-700 border border-gray-200 px-4 py-2 rounded-lg font-medium hover:bg-gray-50 transition-colors;
}
.input-field {
    @apply bg-gray-50 border border-gray-200 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5 transition-all outline-none;
}
</style>
