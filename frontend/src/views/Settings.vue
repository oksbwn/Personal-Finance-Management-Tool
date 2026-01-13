<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'

const notify = useNotificationStore()

const activeTab = ref('accounts') // Defaulting to accounts for now or keeping it as 'rules'
const categories = ref<any[]>([])

// Accounts State
const accounts = ref<any[]>([])
const loading = ref(true)
const showAccountModal = ref(false)
const editingAccountId = ref<string | null>(null)
const newAccount = ref({
    name: '',
    type: 'BANK',
    currency: 'INR',
    account_mask: '',
    balance: 0,
    owner_name: '',
    is_verified: true
})

const searchQuery = ref('')
const verifiedAccounts = computed(() => {
    let filtered = accounts.value.filter(a => a.is_verified !== false)
    if (searchQuery.value) {
        filtered = filtered.filter(a => a.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
    }
    return filtered
})
const untrustedAccounts = computed(() => accounts.value.filter(a => a.is_verified === false))

const accountMetrics = computed(() => {
    return {
        total: accounts.value.reduce((sum, a) => sum + (a.balance || 0), 0),
        cash: accounts.value.filter(a => a.type === 'CASH').reduce((sum, a) => sum + (a.balance || 0), 0),
        bank: accounts.value.filter(a => a.type === 'BANK').reduce((sum, a) => sum + (a.balance || 0), 0),
        credit: accounts.value.filter(a => a.type === 'CREDIT').reduce((sum, a) => sum + (a.balance || 0), 0),
    }
})

// Rules/Categories State
const rules = ref<any[]>([])
const filteredRules = computed(() => {
    if (!searchQuery.value) return rules.value
    const q = searchQuery.value.toLowerCase()
    return rules.value.filter(r => 
        r.name.toLowerCase().includes(q) || 
        r.category.toLowerCase().includes(q) ||
        r.keywords.some((k: string) => k.toLowerCase().includes(q))
    )
})
const suggestions = ref<any[]>([])
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const ruleToDelete = ref<string | null>(null)

const isEditing = ref(false)
const editingId = ref<string | null>(null)
const newRule = ref({
    name: '',
    category: '',
    keywords: ''
})

const showCategoryModal = ref(false)
const showDeleteCategoryConfirm = ref(false)
const categoryToDelete = ref<string | null>(null)
const isEditingCategory = ref(false)
const editingCategoryId = ref<string | null>(null)
const newCategory = ref({ name: '', icon: '🏷️' })

const categoryOptions = computed(() => {
    return categories.value.map(c => ({
        label: `${c.icon} ${c.name}`,
        value: c.name
    }))
})

async function fetchData() {
    loading.value = true
    try {
        const [rulesRes, suggestionsRes, catsRes, accountsRes] = await Promise.all([
            financeApi.getRules(),
            financeApi.getRuleSuggestions(),
            financeApi.getCategories(),
            financeApi.getAccounts()
        ])
        rules.value = rulesRes.data
        suggestions.value = suggestionsRes.data
        categories.value = catsRes.data
        accounts.value = accountsRes.data
    } catch (err) {
        console.error("Failed to fetch data", err)
        notify.error("Failed to load settings data")
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchData()
})

// --- Account Functions ---
function openCreateAccountModal() {
    editingAccountId.value = null
    newAccount.value = { name: '', type: 'BANK', currency: 'INR', account_mask: '', balance: 0, owner_name: '', is_verified: true }
    showAccountModal.value = true
}

function openEditAccountModal(account: any) {
    editingAccountId.value = account.id
    newAccount.value = {
        name: account.name,
        type: account.type,
        currency: account.currency,
        account_mask: account.account_mask || '',
        owner_name: account.owner_name || '',
        balance: account.balance,
        is_verified: true 
    }
    showAccountModal.value = true
}

async function handleAccountSubmit() {
    try {
        if (editingAccountId.value) {
            await financeApi.updateAccount(editingAccountId.value, newAccount.value)
            notify.success("Account updated")
        } else {
            await financeApi.createAccount(newAccount.value)
            notify.success("Account created")
        }
        showAccountModal.value = false
        fetchData()
    } catch (e) {
        notify.error("Failed to save account")
    }
}

const getOwnerIcon = (name: string) => {
    const n = name.toLowerCase()
    if (n.includes('dad') || n.includes('father')) return '👨'
    if (n.includes('mom') || n.includes('mother')) return '👩'
    if (n.includes('kid') || n.includes('child')) return '🧒'
    if (n.includes('grand')) return '🧓'
    return '👤'
}
// End of script logic

// --- Rule Functions ---
async function deleteRule(id: string) {
    ruleToDelete.value = id
    showDeleteConfirm.value = true
}

async function confirmDelete() {
    if (!ruleToDelete.value) return
    try {
        await financeApi.deleteRule(ruleToDelete.value)
        notify.success("Rule deleted")
        fetchData()
    } catch (err) {
        notify.error("Failed to delete rule")
    } finally {
        showDeleteConfirm.value = false
        ruleToDelete.value = null
    }
}

function openAddModal() {
    isEditing.value = false
    editingId.value = null
    newRule.value = { name: '', category: '', keywords: '' }
    showModal.value = true
}

function openEditModal(rule: any) {
    isEditing.value = true
    editingId.value = rule.id
    newRule.value = {
        name: rule.name,
        category: rule.category,
        keywords: rule.keywords.join(', ')
    }
    showModal.value = true
}

async function approveSuggestion(s: any) {
    try {
        await financeApi.createRule({
            name: s.name,
            category: s.category,
            keywords: s.keywords,
            priority: 5
        })
        notify.success(`Rule for "${s.name}" approved!`)
        fetchData()
    } catch (err) {
        console.error(err)
        notify.error("Failed to approve rule")
    }
}

async function saveRule() {
    if (!newRule.value.name || !newRule.value.category || !newRule.value.keywords) return
    
    // Parse keywords: comma separated -> list
    const keywordList = newRule.value.keywords.split(',').map(k => k.trim())
    const payload = {
        ...newRule.value,
        keywords: keywordList,
        priority: 10
    }

    try {
        if (isEditing.value && editingId.value) {
             await financeApi.updateRule(editingId.value, payload)
             notify.success("Rule updated successfully!")
        } else {
             await financeApi.createRule(payload)
             notify.success("New rule created successfully!")
        }
        
        showModal.value = false
        newRule.value = { name: '', category: '', keywords: '' }
        fetchData()
    } catch (err) {
        console.error(err)
        notify.error("Failed to save rule")
    }
}

// --- Category Functions ---
function openAddCategoryModal() {
    isEditingCategory.value = false
    editingCategoryId.value = null
    newCategory.value = { name: '', icon: '🏷️' }
    showCategoryModal.value = true
}

function openEditCategoryModal(cat: any) {
    isEditingCategory.value = true
    editingCategoryId.value = cat.id
    newCategory.value = { name: cat.name, icon: cat.icon }
    showCategoryModal.value = true
}

async function saveCategory() {
    if (!newCategory.value.name) return
    try {
        if (isEditingCategory.value && editingCategoryId.value) {
            await financeApi.updateCategory(editingCategoryId.value, newCategory.value)
            notify.success("Category updated")
        } else {
            await financeApi.createCategory(newCategory.value)
            notify.success("Category created")
        }
        showCategoryModal.value = false
        fetchData()
    } catch (err) {
        notify.error("Failed to save category")
    }
}


function getCategoryDisplay(name: string) {
    if (!name) return '📝 General'
    const cat = categories.value.find(c => c.name === name)
    return cat ? `${cat.icon || '🏷️'} ${cat.name}` : `🏷️ ${name}`
}

async function deleteCategory(id: string) {
    categoryToDelete.value = id
    showDeleteCategoryConfirm.value = true
}

async function confirmDeleteCategory() {
    if (!categoryToDelete.value) return
    try {
        await financeApi.deleteCategory(categoryToDelete.value)
        notify.success("Category deleted")
        fetchData()
    } catch (err) {
        notify.error("Failed to delete category")
    } finally {
        showDeleteCategoryConfirm.value = false
    }
}

</script>

<template>
    <MainLayout>
        <div class="settings-view">
            <!-- New Premium Header -->
            <div class="page-header-compact">
                <div class="header-left">
                    <h1 class="page-title">Settings</h1>
                    <div class="header-tabs">
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'accounts' }" 
                            @click="activeTab = 'accounts'; searchQuery = ''"
                        >
                            Accounts
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'rules' }" 
                            @click="activeTab = 'rules'; searchQuery = ''"
                        >
                            Rules
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'categories' }" 
                            @click="activeTab = 'categories'; searchQuery = ''"
                        >
                            Categories
                        </button>
                    </div>
                </div>

                <div class="header-right-actions">
                    <div class="search-box-compact">
                        <span class="search-icon">🔍</span>
                        <input 
                            v-model="searchQuery" 
                            :placeholder="activeTab === 'accounts' ? 'Search accounts...' : 'Search rules...'" 
                        />
                    </div>
                    <div class="header-actions">
                        <button v-if="activeTab === 'accounts'" @click="openCreateAccountModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> Add Account
                        </button>
                        <button v-if="activeTab === 'rules'" @click="openAddModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> New Rule
                        </button>
                        <button v-if="activeTab === 'categories'" @click="openAddCategoryModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> New Category
                        </button>
                    </div>
                </div>
            </div>

            <div v-if="loading" class="loading-state">
                <div class="loader-spinner"></div>
                <p>Loading your preferences...</p>
            </div>

            <!-- ACCOUNTS TAB -->
            <div v-else-if="activeTab === 'accounts'" class="tab-content animate-in">
                <!-- Account Summary Widgets -->
                <div class="summary-widgets">
                    <div class="mini-stat-card glass h-glow-primary">
                        <div class="stat-top">
                            <span class="stat-label">Total Liquid Wealth</span>
                            <span class="stat-icon-bg gray">⚖️</span>
                        </div>
                        <div class="stat-value">₹ {{ accountMetrics.total.toLocaleString() }}</div>
                    </div>
                    <div class="mini-stat-card glass h-glow-success">
                        <div class="stat-top">
                            <span class="stat-label">Bank Balance</span>
                            <span class="stat-icon-bg green">🏦</span>
                        </div>
                        <div class="stat-value">₹ {{ accountMetrics.bank.toLocaleString() }}</div>
                    </div>
                    <div class="mini-stat-card glass h-glow-warning">
                        <div class="stat-top">
                            <span class="stat-label">Cash on Hand</span>
                            <span class="stat-icon-bg yellow">💵</span>
                        </div>
                        <div class="stat-value">₹ {{ accountMetrics.cash.toLocaleString() }}</div>
                    </div>
                    <div class="mini-stat-card glass h-glow-danger">
                        <div class="stat-top">
                            <span class="stat-label">Credit Liability</span>
                            <span class="stat-icon-bg red">💳</span>
                        </div>
                        <div class="stat-value">₹ {{ accountMetrics.credit.toLocaleString() }}</div>
                    </div>
                </div>

                <!-- Untrusted Accounts -->
                <div v-if="untrustedAccounts.length > 0" class="alert-section">
                    <h2 class="section-title warning">⚠️ New Detected Accounts</h2>
                    <div class="settings-grid">
                        <div v-for="acc in untrustedAccounts" :key="acc.id" class="glass-card untrusted pulse-border">
                            <div class="card-top">
                                <div class="card-main">
                                    <span class="card-label">Untrusted Source</span>
                                    <h3 class="card-name">{{ acc.name }}</h3>
                                </div>
                                <button @click="openEditAccountModal(acc)" class="btn-verify">Verify</button>
                            </div>
                            <div class="card-bottom">
                                <span class="card-balance">₹ {{ Number(acc.balance || 0).toLocaleString() }}</span>
                                <span class="card-meta">Found via SMS</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Verified Accounts -->
                <div class="settings-grid">
                    <div v-for="acc in verifiedAccounts" :key="acc.id" class="glass-card premium-hover">
                        <div class="card-top">
                            <div class="card-main">
                                <div class="card-type-header">
                                    <span class="type-dot" :class="acc.type.toLowerCase()"></span>
                                    <span class="card-label">{{ acc.type }}</span>
                                </div>
                                <h3 class="card-name">{{ acc.name }}</h3>
                            </div>
                            <button @click="openEditAccountModal(acc)" class="btn-icon-circle">✏️</button>
                        </div>
                        <div class="card-bottom">
                            <span class="card-balance">₹ {{ Number(acc.balance || 0).toLocaleString() }}</span>
                            <div class="card-pills">
                                <span class="owner-badge">
                                    {{ getOwnerIcon(acc.owner_name) }} {{ acc.owner_name || 'Family' }}
                                </span>
                                <span v-if="acc.account_mask" class="mask-badge">••{{ acc.account_mask }}</span>
                            </div>
                        </div>
                    </div>

                    <div v-if="verifiedAccounts.length === 0 && !searchQuery" class="empty-card" @click="openCreateAccountModal">
                        <span class="empty-plus">+</span>
                        <p>Track a new account</p>
                    </div>
                    <div v-else-if="verifiedAccounts.length === 0" class="empty-placeholder">
                        <p>No accounts match your search.</p>
                    </div>
                </div>
            </div>

            <!-- RULES TAB -->
            <div v-else-if="activeTab === 'rules'" class="tab-content animate-in">
                <!-- Suggestions -->
                <div v-if="suggestions.length > 0 && !searchQuery" class="alert-section">
                    <h2 class="section-title info">💡 Smart Suggestions</h2>
                    <div class="settings-grid">
                        <div v-for="s in suggestions" :key="s.name" class="glass-card suggestion glow-border-blue">
                            <div class="card-top">
                                <div class="card-main">
                                    <h3 class="card-name">{{ s.name }}</h3>
                                    <div class="rule-flow">
                                        <span class="keyword-tag">{{ s.keywords[0] }}</span>
                                        <span class="arrow">→</span>
                                        <span class="category-pill-sm">{{ getCategoryDisplay(s.category) }}</span>
                                    </div>
                                </div>
                                <button @click="approveSuggestion(s)" class="btn-approve">Approve</button>
                            </div>
                            <div class="card-meta">Based on {{ s.confidence }} manual entries</div>
                        </div>
                    </div>
                </div>

                <!-- Existing Rules -->
                <div class="settings-grid">
                    <div v-for="rule in filteredRules" :key="rule.id" class="glass-card rule-entry premium-hover">
                        <div class="card-top">
                            <div class="card-main">
                                <h3 class="card-name">{{ rule.name }}</h3>
                                <span class="category-pill-sm">{{ getCategoryDisplay(rule.category) }}</span>
                            </div>
                            <div class="card-actions">
                                <button @click="openEditModal(rule)" class="btn-icon-circle">✏️</button>
                                <button @click="deleteRule(rule.id)" class="btn-icon-circle danger">🗑️</button>
                            </div>
                        </div>
                        <div class="card-keywords">
                            <span v-for="k in rule.keywords" :key="k" class="keyword-tag">{{ k }}</span>
                        </div>
                    </div>
                </div>
                
                <div v-if="filteredRules.length === 0" class="empty-placeholder">
                    <p>{{ searchQuery ? 'No rules match your search.' : 'No rules found. Define rules to automate categorization.' }}</p>
                </div>
            </div>

            <!-- CATEGORIES TAB -->
            <div v-else-if="activeTab === 'categories'" class="tab-content animate-in">
                <div class="settings-grid">
                    <div v-for="cat in categories" :key="cat.id" class="glass-card category">
                        <div class="cat-body">
                            <span class="cat-icon-large">{{ cat.icon }}</span>
                            <h3 class="card-name">{{ cat.name }}</h3>
                        </div>
                        <div class="card-actions">
                            <button @click="openEditCategoryModal(cat)" class="btn-icon-circle">✏️</button>
                            <button @click="deleteCategory(cat.id)" class="btn-icon-circle danger">🗑️</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Account Modal -->
        <div v-if="showAccountModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ editingAccountId ? 'Edit Account' : 'New Account' }}</h2>
                    <button class="btn-icon-circle" @click="showAccountModal = false">✕</button>
                </div>

                <form @submit.prevent="handleAccountSubmit" class="form-compact">
                    <div class="form-group">
                        <label class="form-label">Account Name</label>
                        <input v-model="newAccount.name" class="form-input" required placeholder="e.g. HDFC Savings" />
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Owner (Person)</label>
                        <CustomSelect 
                            v-model="newAccount.owner_name" 
                            :options="[
                                { label: 'Shared / Family', value: '' },
                                { label: 'Dad', value: 'Dad' },
                                { label: 'Mom', value: 'Mom' },
                                { label: 'Kid', value: 'Kid' }
                            ]"
                            placeholder="Select Owner"
                        />
                    </div>

                    <div class="form-row">
                        <div class="form-group half">
                            <label class="form-label">Type</label>
                            <CustomSelect 
                                v-model="newAccount.type"
                                :options="[
                                    { label: 'Bank Account', value: 'BANK' },
                                    { label: 'Cash Wallet', value: 'CASH' },
                                    { label: 'Investment', value: 'INVESTMENT' },
                                    { label: 'Credit Card', value: 'CREDIT' }
                                ]"
                            />
                        </div>
                        <div class="form-group half">
                            <label class="form-label">Currency</label>
                            <CustomSelect 
                                v-model="newAccount.currency"
                                :options="[
                                    { label: 'INR - Indian Rupee', value: 'INR' },
                                    { label: 'USD - US Dollar', value: 'USD' }
                                ]"
                            />
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Account Mask (Last 4 Digits)</label>
                        <input v-model="newAccount.account_mask" class="form-input" placeholder="e.g. 1234" maxlength="4" />
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Current Balance</label>
                        <input type="number" v-model.number="newAccount.balance" class="form-input" step="0.01" />
                    </div>

                    <div class="modal-footer">
                        <button type="button" @click="showAccountModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Changes</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Add/Edit Rule Modal -->
        <div v-if="showModal" class="modal-overlay-global">
            <div class="modal-global glass">
                 <div class="modal-header">
                    <h2 class="modal-title">{{ isEditing ? 'Edit Rule' : 'New Rule' }}</h2>
                    <button class="btn-icon-circle" @click="showModal = false">✕</button>
                </div>
                
                <form @submit.prevent="saveRule" class="form-compact">
                    <div class="form-group">
                        <label class="form-label">Rule Name</label>
                        <input v-model="newRule.name" class="form-input" required placeholder="e.g. Ride Apps" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <CustomSelect 
                            v-model="newRule.category" 
                             :options="categoryOptions"
                            placeholder="Select Category"
                        />
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Keywords (Comma Separated)</label>
                        <textarea v-model="newRule.keywords" class="form-input" rows="3" placeholder="Uber, Lyft, Ola"></textarea>
                    </div>

                    <div class="modal-footer">
                         <button type="button" @click="showModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Rule</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- Add/Edit Category Modal -->
        <div v-if="showCategoryModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ isEditingCategory ? 'Edit Category' : 'New Category' }}</h2>
                    <button class="btn-icon-circle" @click="showCategoryModal = false">✕</button>
                </div>
                
                <form @submit.prevent="saveCategory" class="form-compact">
                     <div class="form-group">
                        <label class="form-label">Icon (Emoji)</label>
                        <input v-model="newCategory.icon" class="form-input emoji-input" required />
                    </div>
                    <div class="form-group">
                        <label class="form-label">Category Name</label>
                        <input v-model="newCategory.name" class="form-input" required placeholder="e.g. Subscriptions" />
                    </div>
                    <div class="modal-footer">
                         <button type="button" @click="showCategoryModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Category</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Confirmations -->
        <div v-if="showDeleteConfirm" class="modal-overlay-global">
            <div class="modal-global glass alert">
                <h2 class="modal-title">Delete Rule?</h2>
                <p>This will stop automatic categorization for matching transactions.</p>
                <div class="modal-footer">
                    <button @click="showDeleteConfirm = false" class="btn-secondary">Keep it</button>
                    <button @click="confirmDelete" class="btn-danger">Delete Rule</button>
                </div>
            </div>
        </div>

        <div v-if="showDeleteCategoryConfirm" class="modal-overlay-global">
            <div class="modal-global glass alert">
                <h2 class="modal-title">Delete Category?</h2>
                <p>Existing transactions in this category will become uncategorized.</p>
                <div class="modal-footer">
                    <button @click="showDeleteCategoryConfirm = false" class="btn-secondary">Cancel</button>
                    <button @click="confirmDeleteCategory" class="btn-danger">Delete</button>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
.settings-view {
    padding-bottom: 4rem;
}

/* Premium Header Styling */
.page-header-compact {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    gap: 1.5rem;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.header-right-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.search-box-compact {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: white;
    padding: 0.375rem 0.75rem;
    border-radius: 0.625rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    width: 200px;
    transition: all 0.2s;
}

.search-box-compact:focus-within {
    width: 260px;
    border-color: #4f46e5;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.08);
}

.search-icon { font-size: 0.8rem; opacity: 0.5; }

.search-box-compact input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 0.8125rem;
    width: 100%;
}

.page-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    margin: 0;
    letter-spacing: -0.025em;
}

/* Summary Widgets */
.summary-widgets {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.875rem;
    margin-bottom: 1.25rem;
}

.mini-stat-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.875rem;
    padding: 0.875rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    transition: all 0.2s;
}

.mini-stat-card:hover {
    transform: translateY(-2px);
    border-color: #d1d5db;
}

.stat-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.stat-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stat-icon-bg {
    width: 32px; height: 32px;
    border-radius: 0.5rem;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
}

.stat-icon-bg.gray { background: #f3f4f6; }
.stat-icon-bg.green { background: #ecfdf5; }
.stat-icon-bg.yellow { background: #fffbeb; }
.stat-icon-bg.red { background: #fef2f2; }

.stat-value {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.025em;
}

/* Glow Effects */
.h-glow-primary:hover { box-shadow: 0 4px 15px rgba(79, 70, 229, 0.1); }
.h-glow-success:hover { box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1); }
.h-glow-warning:hover { box-shadow: 0 4px 15px rgba(245, 158, 11, 0.1); }
.h-glow-danger:hover { box-shadow: 0 4px 15px rgba(239, 68, 68, 0.1); }

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
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-btn.active {
    background: white;
    color: #111827;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
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

/* Grid & Cards */
.settings-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 0.875rem;
}

.glass-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 1rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    transition: all 0.2s;
}

.glass-card:hover {
    border-color: #d1d5db;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.card-label {
    font-size: 0.6rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 0.125rem;
}

.card-name {
    font-size: 1rem;
    font-weight: 700;
    color: #111827;
    margin: 0;
}

.card-type-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-bottom: 0.125rem;
}

.type-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
}
.type-dot.bank { background: #10b981; }
.type-dot.cash { background: #f59e0b; }
.type-dot.credit { background: #ef4444; }
.type-dot.investment { background: #3b82f6; }

.card-balance {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.025em;
}

.card-bottom {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}

.card-pills {
    display: flex;
    gap: 0.375rem;
}

.owner-badge {
    padding: 0.2rem 0.5rem;
    background: #f3f4f6;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #374151;
}

.mask-badge {
    padding: 0.2rem 0.5rem;
    background: #eef2ff;
    color: #4f46e5;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
}

/* Icons & Buttons */
.btn-icon-circle {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    border: none;
    background: #f9fafb;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.875rem;
}

.btn-icon-circle:hover {
    background: #f3f4f6;
    transform: rotate(15deg);
}

.btn-icon-circle.danger:hover {
    background: #fee2e2;
    color: #dc2626;
}

.btn-verify {
    padding: 0.375rem 0.75rem;
    background: #4f46e5;
    color: white;
    border: none;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
}

/* Specialized Sections */
.alert-section {
    margin-bottom: 1.5rem;
}

.premium-hover:hover {
    transform: translateY(-2px) scale(1.01);
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
}

.pulse-border {
    border: 1px dashed #fbbf24;
    animation: border-pulse 2s infinite ease-in-out;
}

@keyframes border-pulse {
    0% { border-color: rgba(251, 191, 36, 0.4); }
    50% { border-color: rgba(251, 191, 36, 1); }
    100% { border-color: rgba(251, 191, 36, 0.4); }
}

.glow-border-blue {
    border: 1px solid rgba(79, 70, 229, 0.2);
    box-shadow: 0 0 10px rgba(79, 70, 229, 0.05);
}

.section-title {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
}

.section-title.warning { color: #d97706; }
.section-title.info { color: #4f46e5; }

.glass-card.untrusted {
    border: 1px dashed #fbbf24;
    background: #fffbeb;
}

.empty-card {
    border: 2px dashed #e5e7eb;
    border-radius: 1.25rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    cursor: pointer;
    transition: all 0.2s;
    color: #9ca3af;
}

.empty-card:hover {
    border-color: #4f46e5;
    background: #f5f3ff;
    color: #4f46e5;
}

.empty-plus { font-size: 1.5rem; font-weight: 300; margin-bottom: 0.25rem; }

/* Rules Styling */
.rule-flow {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.25rem;
}

.keyword-tag {
    padding: 0.125rem 0.375rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    font-size: 0.7rem;
    color: #4b5563;
}

.category-pill-sm {
    padding: 0.125rem 0.375rem;
    background: #eef2ff;
    color: #4f46e5;
    border-radius: 0.375rem;
    font-size: 0.7rem;
    font-weight: 600;
}

.card-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
}

/* Category Large View */
.glass-card.category {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
}

.cat-body {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.cat-icon-large {
    font-size: 1.5rem;
}

/* States */
.loading-state {
    padding: 3rem 0;
    text-align: center;
    color: #6b7280;
    font-size: 0.875rem;
}

.loader-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #4f46e5;
    border-radius: 50%;
    margin: 0 auto 1rem;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.animate-in {
    animation: slideUp 0.4s ease-out forwards;
}

@keyframes slideUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Modal Enhancements */
.modal-overlay-global {
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(4px);
}

.modal-global.glass {
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.emoji-input {
    font-size: 1.5rem;
    width: 4rem;
    text-align: center;
}

.form-compact .form-group { margin-bottom: 1.25rem; }
.form-row { display: flex; gap: 1rem; }
.half { flex: 1; }

.btn-secondary {
    padding: 0.625rem 1.25rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    font-weight: 600;
    cursor: pointer;
}

.btn-danger {
    padding: 0.625rem 1.25rem;
    background: #dc2626;
    color: white;
    border: none;
    border-radius: 0.75rem;
    font-weight: 600;
    cursor: pointer;
}
</style>
