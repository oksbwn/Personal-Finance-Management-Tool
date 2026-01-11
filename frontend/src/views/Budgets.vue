<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'

const notify = useNotificationStore()

const budgets = ref<any[]>([])
const categories = ref<any[]>([])
const loading = ref(true)

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
        <div class="page-header">
            <div>
                <h1>Budgets (Monthly)</h1>
                <p class="subtitle">Track your spending for the current month.</p>
            </div>
            <div class="header-actions">
                 <button v-if="!overallBudget" class="btn btn-outline" @click="openSetBudgetModal(true)">+ Set Overall Limit</button>
                 <button class="btn btn-primary" @click="openSetBudgetModal(false)">+ Set Category Budget</button>
            </div>
        </div>

        <div v-if="loading" class="loading">Loading...</div>

        <div v-else>
            <!-- Overall Budget Hero Card -->
            <div v-if="overallBudget" class="card overall-card">
                 <div class="overall-header">
                     <div class="overall-title">
                         <h2>🏁 Overall Monthly Limit</h2>
                         <div class="overall-stats">
                             <span class="badgex">Limit: ₹ {{ Number(overallBudget.amount_limit).toLocaleString() }}</span>
                         </div>
                     </div>
                     <div class="actions">
                         <button @click="editBudget(overallBudget)" class="btn-icon">✏️</button>
                         <button @click="deleteBudget(overallBudget.id)" class="btn-icon danger">🗑️</button>
                     </div>
                 </div>
                 
                 <div class="main-progress">
                      <div class="progress-labels-lg">
                          <span class="big-amt">₹ {{ Number(overallBudget.spent).toLocaleString() }}</span>
                          <span class="label-text">spent of ₹ {{ Number(overallBudget.amount_limit).toLocaleString() }}</span>
                      </div>
                      <div class="progress-bar-bg lg">
                            <div class="progress-bar-fill" 
                                 :style="{ width: Math.min(overallBudget.percentage, 100) + '%' }"
                                 :class="{ 
                                     'warning': overallBudget.percentage > 80 && overallBudget.percentage <= 100,
                                     'danger': overallBudget.percentage > 100 
                                 }"
                            ></div>
                        </div>
                        <div class="remaining-text lg" :class="{ 'over': overallBudget.remaining < 0 }">
                            {{ overallBudget.remaining >= 0 ? `₹ ${Number(overallBudget.remaining).toLocaleString()} remaining` : `Over by ₹ ${Math.abs(Number(overallBudget.remaining)).toLocaleString()}` }}
                        </div>
                 </div>
            </div>

            <!-- Summary Cards (Secondary) -->
            <div class="grid summary-grid">
                <div class="card summary-card">
                    <h3>Total Budgeted</h3>
                    <p class="amount">₹ {{ effectiveTotalBudget.toLocaleString() }}</p>
                </div>
                <div class="card summary-card">
                    <h3>Total Spent</h3>
                    <p class="amount">₹ {{ totalSpent.toLocaleString() }}</p>
                </div>
                 <div class="card summary-card">
                    <h3>Remaining</h3>
                     <p class="amount" :class="{ 'negative': totalRemaining < 0 }">₹ {{ totalRemaining.toLocaleString() }}</p>
                </div>
            </div>

            <h3 class="section-title">Category Budgets</h3>
            <!-- Budgets List -->
            <div class="budgets-list">
                <div v-for="b in categoryBudgets" :key="b.id" class="card budget-item">
                    <div class="budget-header">
                        <div class="cat-info">
                            <span class="cat-name">{{ getCategoryDisplay(b.category) }}</span>
                        </div>
                        <div class="budget-actions">
                            <button @click="editBudget(b)" class="btn-icon">✏️</button>
                            <button @click="deleteBudget(b.id)" class="btn-icon danger">🗑️</button>
                        </div>
                    </div>
                    
                    <div class="progress-area">
                        <div class="progress-labels">
                            <span>₹ {{ Number(b.spent).toLocaleString() }} spent</span>
                            <span>Limit: ₹ {{ Number(b.amount_limit).toLocaleString() }}</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" 
                                 :style="{ width: Math.min(b.percentage, 100) + '%' }"
                                 :class="{ 
                                     'warning': b.percentage > 80 && b.percentage <= 100,
                                     'danger': b.percentage > 100 
                                 }"
                            ></div>
                        </div>
                        <div class="remaining-text" :class="{ 'over': b.remaining < 0 }">
                            {{ b.remaining >= 0 ? `₹ ${Number(b.remaining).toLocaleString()} left` : `Over by ₹ ${Math.abs(Number(b.remaining)).toLocaleString()}` }}
                        </div>
                    </div>
                </div>

                <div v-if="categoryBudgets.length === 0" class="empty-state">
                    <p>No category budgets set.</p>
                </div>
            </div>
        </div>

        <!-- Modal -->
        <div v-if="showModal" class="modal-overlay-global">
            <div class="modal-global">
                <div class="modal-header">
                    <h2 class="modal-title">{{ newBudget.category === 'OVERALL' ? 'Set Overall Limit' : 'Set Category Budget' }}</h2>
                    <button class="btn-icon" @click="showModal = false">✕</button>
                </div>
                <form @submit.prevent="saveBudget">
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
                        <input type="number" v-model="newBudget.amount_limit" class="form-input" required placeholder="5000" />
                    </div>
                    <div class="modal-footer">
                        <button type="button" @click="showModal = false" class="btn btn-outline">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
    </MainLayout>
</template>


<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
.subtitle { color: var(--color-text-muted); margin-top: 0.5rem; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.summary-card { padding: 1.5rem; text-align: center; }
.summary-card h3 { font-size: 0.9rem; color: var(--color-text-muted); text-transform: uppercase; margin-bottom: 0.5rem; }
.summary-card .amount { font-size: 1.5rem; font-weight: 700; color: var(--color-text-main); }
.summary-card .amount.negative { color: var(--color-danger); }

.budgets-list { display: flex; flex-direction: column; gap: 1rem; }
.budget-item { padding: 1.5rem; }

.budget-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.cat-name { font-size: 1.1rem; font-weight: 600; }

.progress-labels { display: flex; justify-content: space-between; font-size: 0.9rem; color: var(--color-text-muted); margin-bottom: 0.5rem; }
.progress-bar-bg { background: var(--color-background); height: 12px; border-radius: 6px; overflow: hidden; border: 1px solid var(--color-border); }
.progress-bar-fill { height: 100%; background: var(--color-success); border-radius: 6px; transition: width 0.3s ease; }
.progress-bar-fill.warning { background: #facc15; } /* Yellow-400 */
.progress-bar-fill.danger { background: var(--color-danger); }

.remaining-text { font-size: 0.85rem; margin-top: 0.5rem; text-align: right; color: var(--color-text-muted); }
.remaining-text.over { color: var(--color-danger); font-weight: 600; }

.loading { text-align: center; padding: 2rem; color: var(--color-text-muted); }
.empty-state { text-align: center; padding: 3rem; background: var(--color-surface); border: 2px dashed var(--color-border); border-radius: 1rem; color: var(--color-text-muted); }

/* Globals reused */
.modal-overlay-global { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal-global { background: var(--color-surface); padding: 2rem; border-radius: 1rem; width: 100%; max-width: 500px; box-shadow: var(--shadow-xl); }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-title { margin: 0; font-size: 1.25rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
.form-group { margin-bottom: 1rem; }
.form-label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
.form-input { width: 100%; padding: 0.75rem; border: 1px solid var(--color-border); border-radius: 0.5rem; background: var(--color-background); color: var(--color-text-main); }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 1.2rem; padding: 0.2rem; }
.btn-icon:hover { background: var(--color-background); border-radius: 4px; }
.danger { color: var(--color-danger); }

/* Overall Card Styles */
.overall-card { background: linear-gradient(135deg, var(--color-surface), var(--color-background)); border: 2px solid var(--color-primary); padding: 2rem; margin-bottom: 2rem; }
.overall-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; }
.overall-title h2 { margin: 0; font-size: 1.5rem; color: var(--color-primary); display: flex; align-items: center; gap: 0.5rem; }
.progress-labels-lg { display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.75rem; }
.big-amt { font-size: 2.5rem; font-weight: 800; color: var(--color-text-main); line-height: 1; }
.label-text { color: var(--color-text-muted); font-size: 1.1rem; }

.progress-bar-bg.lg { height: 24px; border-radius: 12px; }
.remaining-text.lg { font-size: 1rem; margin-top: 1rem; font-weight: 500; }

.section-title { font-size: 1.25rem; margin-bottom: 1rem; color: var(--color-text-main); margin-top: 2rem; }
.header-actions { display: flex; gap: 1rem; }
</style>
