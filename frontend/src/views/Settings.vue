<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi, aiApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import { useSettingsStore } from '@/stores/settings'

const notify = useNotificationStore()
const settingsStore = useSettingsStore()
import { useCurrency } from '@/composables/useCurrency'

const { formatAmount } = useCurrency()

function saveSettings() {
    notify.success("Settings saved")
}

const activeTab = ref('general')
const categories = ref<any[]>([])

// Accounts State
const accounts = ref<any[]>([])
const emailConfigs = ref<any[]>([])
const tenants = ref<any[]>([])
const familyMembers = ref<any[]>([])
const currentUser = ref<any>(null)
const loading = ref(true)
const isSyncing = ref(false)
const syncStatus = ref<any>(null)

// Tenant Rename Modal State
const showTenantModal = ref(false)
const tenantForm = ref({ id: '', name: '' })

// Email Config Modal State
const showEmailModal = ref(false)
const newEmailConfig = ref({
    email: '',
    password: '',
    imap_server: 'imap.gmail.com',
    folder: 'INBOX'
})
const showAccountModal = ref(false)
const editingAccountId = ref<string | null>(null)
const newAccount = ref({
    name: '',
    type: 'BANK',
    currency: 'INR',
    account_mask: '',
    balance: 0,
    credit_limit: null,
    is_verified: true,
    tenant_id: '',
    owner_id: ''
})

// Family Member Modal State
const showMemberModal = ref(false)
const isEditingMember = ref(false)
const memberForm = ref({
    id: '',
    email: '',
    full_name: '',
    password: '',
    role: 'ADULT',
    avatar: '👨‍💼'
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
    let total = 0
    let cash = 0
    let bank = 0
    let credit = 0

    accounts.value.forEach(a => {
        const bal = Number(a.balance || 0)
        if (a.type === 'CREDIT_CARD' || a.type === 'LOAN') {
            credit += bal
            total -= bal
        } else {
            // Bank, Cash, Investment, Wallet
            total += bal
            if (a.type === 'BANK') bank += bal
            if (a.type === 'WALLET' || a.type === 'CASH') cash += bal
        }
    })

    return { total, cash, bank, credit }
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

// Account Deletion State
const showAccountDeleteConfirm = ref(false)
const accountToDelete = ref<any>(null)
const accountTxCount = ref(0)
const isDeletingAccount = ref(false)

async function deleteAccountRequest(account: any) {
    accountToDelete.value = account
    accountTxCount.value = 0
    try {
        const res = await financeApi.getAccountTransactionCount(account.id)
        accountTxCount.value = res.data.count
    } catch (e) {
        console.error("Failed to fetch tx count", e)
    }
    showAccountDeleteConfirm.value = true
}

async function confirmAccountDelete() {
    if (!accountToDelete.value) return
    isDeletingAccount.value = true
    try {
        await financeApi.deleteAccount(accountToDelete.value.id)
        notify.success("Account and related data removed")
        showAccountDeleteConfirm.value = false
        fetchData()
    } catch (e) {
        notify.error("Failed to delete account")
    } finally {
        isDeletingAccount.value = false
        accountToDelete.value = null
    }
}

const showCategoryModal = ref(false)
const showDeleteCategoryConfirm = ref(false)
const categoryToDelete = ref<string | null>(null)
const isEditingCategory = ref(false)
const editingCategoryId = ref<string | null>(null)

// AI Integration State
const aiForm = ref({
    provider: 'gemini',
    model_name: 'gemini-1.5-flash',
    api_key: '',
    is_enabled: false,
    prompts: {
        parsing: "Extract transaction details from the following message. Return JSON with: amount (number), date (DD/MM/YYYY), recipient (string), account_mask (4 digits), ref_id (string or null), type (DEBIT/CREDIT)."
    } as Record<string, string>,
    has_api_key: false
})
const aiModels = ref<{label: string, value: string}[]>([])
const aiTesting = ref(false)
const aiTestResult = ref<any>(null)
const aiTestMessage = ref("Spent Rs 500.50 at Amazon using card ending in 1234 on 14/01/2026")

async function fetchAiModels() {
    try {
        const res = await aiApi.listModels(aiForm.value.provider, aiForm.value.api_key)
        if (res.data && res.data.length > 0) {
            aiModels.value = res.data
        } else if (aiModels.value.length === 0) {
            // Fallback if none found and we have none cached
            aiModels.value = [
                { label: 'Gemini 1.5 Flash (Fast)', value: 'models/gemini-1.5-flash' },
                { label: 'Gemini 1.5 Pro (Best)', value: 'models/gemini-1.5-pro' }
            ]
        }
    } catch (e) {
        console.error("Failed to fetch AI models", e)
    }
}

async function fetchAiSettings() {
    try {
        const res = await aiApi.getSettings()
        const data = res.data
        aiForm.value = { 
            ...aiForm.value, 
            ...data, 
            api_key: '', 
            prompts: data.prompts || aiForm.value.prompts 
        }
        // Fetch models after loading settings
        fetchAiModels()
    } catch (e) {
        console.error("Failed to load AI settings", e)
    }
}

async function saveAiSettings() {
    try {
        await aiApi.updateSettings(aiForm.value)
        notify.success("AI settings updated")
        fetchAiSettings()
    } catch (e) {
        notify.error("Failed to update AI settings")
    }
}

async function testAi() {
    if (aiTesting.value) return
    aiTesting.value = true
    aiTestResult.value = null
    try {
        const res = await aiApi.testConnection(aiTestMessage.value)
        aiTestResult.value = res.data
        if (res.data.status === 'success') {
            notify.success("AI test successful")
        } else {
            notify.warning("AI test failed")
        }
    } catch (e) {
        notify.error("AI test error")
    } finally {
        aiTesting.value = false
    }
}
const newCategory = ref({ name: '', icon: '🏷️', color: '#3B82F6' })

const categoryOptions = computed(() => {
    return categories.value.map(c => ({
        label: `${c.icon} ${c.name}`,
        value: c.name
    }))
})

async function fetchData() {
    loading.value = true
    try {
        const [accRes, rulesRes, catRes, sugRes, emailRes, tenantRes, usersRes, meRes] = await Promise.all([
            financeApi.getAccounts(),
            financeApi.getRules(),
            financeApi.getCategories(),
            financeApi.getRuleSuggestions(),
            financeApi.getEmailConfigs(),
            financeApi.getTenants(),
            financeApi.getUsers(),
            financeApi.getMe()
        ])
        accounts.value = accRes.data
        rules.value = rulesRes.data
        categories.value = catRes.data
        suggestions.value = sugRes.data
        emailConfigs.value = emailRes.data
        tenants.value = tenantRes.data
        familyMembers.value = usersRes.data
        currentUser.value = meRes.data
        fetchAiSettings()
    } catch (err) {
        console.error('Failed to fetch settings data', err)
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
    newAccount.value = { 
        name: '', type: 'BANK', currency: 'INR', 
        account_mask: '', balance: 0, 
        credit_limit: null,
        is_verified: true,
        tenant_id: tenants.value[0]?.id || '',
        owner_id: ''
    }
    showAccountModal.value = true
}

function openEditAccountModal(account: any, autoVerify: boolean = false) {
    editingAccountId.value = account.id
    newAccount.value = {
        name: account.name,
        type: account.type,
        currency: account.currency,
        account_mask: account.account_mask,
        balance: account.balance,
        credit_limit: account.credit_limit,
        owner_id: account.owner_id,
        tenant_id: account.tenant_id,
        is_verified: autoVerify ? true : account.is_verified
    }
    showAccountModal.value = true
}

async function handleAccountSubmit() {
    try {
        const payload = {
            ...newAccount.value,
            balance: Number(newAccount.value.balance),
            credit_limit: newAccount.value.type === 'CREDIT_CARD' ? Number(newAccount.value.credit_limit) : null
        }
        
        if (editingAccountId.value) {
            await financeApi.updateAccount(editingAccountId.value, payload)
            notify.success("Account updated")
        } else {
            await financeApi.createAccount(payload)
            notify.success("Account created")
        }
        showAccountModal.value = false
        fetchData()
    } catch (e) {
        notify.error("Failed to save account")
    }
}

const resolveOwnerAvatar = (account: any) => {
    if (account.owner_id) {
        const member = familyMembers.value.find(m => m.id === account.owner_id)
        if (member && member.avatar) return member.avatar
    }
    return '👨‍👩‍👧‍👦' // Family icon as fallback
}

const resolveOwnerName = (account: any) => {
    if (account.owner_id) {
        const member = familyMembers.value.find(m => m.id === account.owner_id)
        if (member) return member.full_name || member.email
    }
    return 'Family'
}

const getOwnerIcon = (name: string) => {
    const n = name.toLowerCase()
    if (n.includes('dad') || n.includes('father')) return '👨'
    if (n.includes('mom') || n.includes('mother')) return '👩'
    if (n.includes('kid') || n.includes('child')) return '🧒'
    if (n.includes('grand')) return '🧓'
    return '👤'
}

const getMemberAccountCount = (memberId: string) => {
    return accounts.value.filter(a => a.owner_id === memberId).length
}

const getRoleIcon = (role: string) => {
    switch(role) {
        case 'OWNER': return '👑'
        case 'ADULT': return '🛡️'
        case 'CHILD': return '🧸'
        case 'GUEST': return '👀'
        default: return '👤'
    }
}

const getRoleColorClass = (role: string) => {
    switch(role) {
        case 'OWNER': return 'ring-gold'
        case 'ADULT': return 'ring-blue'
        case 'CHILD': return 'ring-green'
        default: return 'ring-gray'
    }
}
// --- Email UI Logic ---
const showEmailEditModal = ref(false)
const editingEmailConfig = ref<string | null>(null)
const showHistoryModal = ref(false)
const syncLogs = ref<any[]>([])
const selectedHistoryConfigId = ref<string | null>(null)

const emailForm = ref({
    email: '',
    password: '',
    host: 'imap.gmail.com',
    folder: 'INBOX',
    auto_sync: false
})

async function saveEmailConfig() {
    try {
        const payload = {
            email: emailForm.value.email,
            password: emailForm.value.password,
            imap_server: emailForm.value.host,
            folder: emailForm.value.folder,
            auto_sync_enabled: emailForm.value.auto_sync
        }

        if (editingEmailConfig.value) {
            await financeApi.updateEmailConfig(editingEmailConfig.value, payload)
            notify.success("Email configuration updated")
        } else {
            await financeApi.createEmailConfig(payload)
            notify.success("Email configuration added")
        }
        
        showEmailModal.value = false
        showEmailEditModal.value = false
        emailForm.value = { email: '', password: '', host: 'imap.gmail.com', folder: 'INBOX', auto_sync: false }
        fetchData()
    } catch (e) {
        notify.error("Failed to save email config")
    }
}

function openAddEmailModal() {
    emailForm.value = { email: '', password: '', host: 'imap.gmail.com', folder: 'INBOX', auto_sync: false }
    editingEmailConfig.value = null
    showEmailModal.value = true
}

function openEditEmailModal(config: any) {
    emailForm.value = { 
        email: config.email, 
        password: config.password, 
        host: config.imap_server, 
        folder: config.folder,
        auto_sync: config.auto_sync_enabled || false
    }
    editingEmailConfig.value = config.id
    showEmailModal.value = true
}

async function rewindSync(hours: number) {
    if (!editingEmailConfig.value) return
    const configId = editingEmailConfig.value
    
    // Calculate new time: Now - X hours
    const now = new Date()
    now.setHours(now.getHours() - hours)
    
    try {
        await financeApi.updateEmailConfig(configId, { last_sync_at: now.toISOString() })
        notify.info(`Rewound config. Triggering sync...`)
        showEmailModal.value = false
        // Trigger Sync Immediately
        await handleSync(configId)
        fetchData()
    } catch (e) {
        notify.error("Failed to rewind sync")
    }
}

async function resetSyncHistory() {
    if (!editingEmailConfig.value) return
    const configId = editingEmailConfig.value
    if (!confirm("This will force a DEEP SCAN of ALL emails. This takes time. Continue?")) return
    try {
        await financeApi.updateEmailConfig(configId, { reset_sync_history: true })
        notify.info("Deep scan requested. Starting...")
        showEmailModal.value = false
        // Trigger Sync Immediately
        await handleSync(configId)
        fetchData()
    } catch (e) {
        notify.error("Failed to reset sync history")
    }
}

async function deleteEmailConfig(id: string) {
    if (!confirm("Are you sure you want to remove this email account? This will stop future syncs.")) return
    try {
        await financeApi.deleteEmailConfig(id)
        notify.success("Email account removed")
        showEmailModal.value = false
        fetchData()
    } catch (e) {
        notify.error("Failed to remove email config")
    }
}

async function openHistoryModal(config: any) {
    selectedHistoryConfigId.value = config.id
    showHistoryModal.value = true
    syncLogs.value = [] // Reset while loading
    try {
        const res = await financeApi.getEmailSyncLogs(config.id)
        syncLogs.value = res.data
    } catch (e) {
        notify.error("Failed to fetch logs")
    }
}

function formatDateFull(dateStr: string) {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString()
}

function formatDate(dateStr: string) {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString()
}

function getAccountTypeIcon(type: string) {
    const icons: Record<string, string> = {
        'BANK': '🏦',
        'CREDIT_CARD': '💳',
        'LOAN': '💸',
        'WALLET': '👛',
        'INVESTMENT': '📈'
    }
    return icons[type] || '💰'
}

function getAccountTypeLabel(type: string) {
    const labels: Record<string, string> = {
        'BANK': 'Bank account',
        'CREDIT_CARD': 'Credit Card',
        'LOAN': 'Loans / EMIs',
        'WALLET': 'Wallet / Cash',
        'INVESTMENT': 'Investment'
    }
    return labels[type] || type
}


function getLogIcon(status: string) {
    if (status === 'completed') return '✅'
    if (status === 'error') return '❌'
    return '⏳'
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
    newCategory.value = { name: '', icon: '🏷️', color: '#3B82F6' }
    showCategoryModal.value = true
}

function openEditCategoryModal(cat: any) {
    isEditingCategory.value = true
    editingCategoryId.value = cat.id
    newCategory.value = { name: cat.name, icon: cat.icon, color: cat.color || '#3B82F6' }
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

async function handleSync(configId: string) {
    isSyncing.value = true
    syncStatus.value = { status: 'running', configId }
    try {
        const res = await financeApi.syncEmailConfig(configId)
        syncStatus.value = { ...res.data, configId }
        if (res.data.status === 'completed') {
            await fetchData()
        }
    } catch (e: any) {
        syncStatus.value = { status: 'error', message: e.response?.data?.detail || "Sync failed", configId }
    } finally {
        isSyncing.value = false
    }
}

async function handleEmailConfigSubmit() {
    try {
        await financeApi.createEmailConfig(newEmailConfig.value)
        showEmailModal.value = false
        newEmailConfig.value = { email: '', password: '', imap_server: 'imap.gmail.com', folder: 'INBOX' }
        fetchData()
    } catch (err) {
        console.error("Failed to save email config", err)
    }
}


function openRenameTenantModal(tenant: any) {
    tenantForm.value = { id: tenant.id, name: tenant.name }
    showTenantModal.value = true
}

async function handleRenameTenant() {
    if (!tenantForm.value.name) return
    try {
        await financeApi.updateTenant(tenantForm.value.id, { name: tenantForm.value.name })
        notify.success("Family name updated")
        showTenantModal.value = false
        fetchData()
    } catch (err) {
        notify.error("Rename failed")
    }
}

function openAddMemberModal() {
    isEditingMember.value = false
    memberForm.value = {
        id: '',
        email: '',
        full_name: '',
        password: '',
        role: 'ADULT' as any,
        avatar: '👨‍💼'
    }
    showMemberModal.value = true
}

function openEditMemberModal(member: any) {
    isEditingMember.value = true
    memberForm.value = {
        id: member.id,
        email: member.email,
        full_name: member.full_name || '',
        password: '',
        role: member.role,
        avatar: member.avatar || '👤'
    }
    showMemberModal.value = true
}

async function handleMemberSubmit() {
    try {
        if (isEditingMember.value) {
            await financeApi.updateUser(memberForm.value.id, {
                full_name: memberForm.value.full_name,
                avatar: memberForm.value.avatar,
                role: memberForm.value.role,
                password: memberForm.value.password || undefined
            })
            notify.success("Member updated")
        } else {
            await financeApi.createUser(memberForm.value)
            notify.success("Member added successfully")
        }
        showMemberModal.value = false
        fetchData()
    } catch (err: any) {
        notify.error(err.response?.data?.detail || "Action failed")
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
                            :class="{ active: activeTab === 'general' }" 
                            @click="activeTab = 'general'; searchQuery = ''"
                        >
                            General
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'accounts' }" 
                            @click="activeTab = 'accounts'; searchQuery = ''"
                        >
                            Accounts
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'tenants' }" 
                            @click="activeTab = 'tenants'; searchQuery = ''"
                        >
                            Family
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'categories' }" 
                            @click="activeTab = 'categories'; searchQuery = ''"
                        >
                            Categories
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
                            :class="{ active: activeTab === 'emails' }" 
                            @click="activeTab = 'emails'; searchQuery = ''"
                        >
                            Emails
                        </button>
                        <button 
                            class="tab-btn" 
                            :class="{ active: activeTab === 'ai' }" 
                            @click="activeTab = 'ai'; searchQuery = ''"
                        >
                            AI Integration
                        </button>
                    </div>
                </div>

                <div class="header-right-actions">
                    <div class="search-box-compact">
                        <span class="search-icon">🔍</span>
                        <input 
                            v-model="searchQuery" 
                            placeholder="Quick search..." 
                            class="search-input-compact"
                        />
                    </div>
                    <div class="action-buttons-group">
                        <button v-if="activeTab === 'accounts'" @click="openCreateAccountModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> Add Account
                        </button>
                        <button v-if="activeTab === 'emails'" @click="showEmailModal = true" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> Add Email
                        </button>
                        <button v-if="activeTab === 'rules'" @click="openAddModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> New Rule
                        </button>
                        <button v-if="activeTab === 'categories'" @click="openAddCategoryModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> New Category
                        </button>
                        <button v-if="activeTab === 'tenants'" @click="openAddMemberModal" class="btn-primary-glow">
                            <span class="btn-icon-plus">+</span> Add Member
                        </button>
                    </div>
                </div>
            </div>

            <div v-if="loading" class="loading-state">
                <div class="loader-spinner"></div>
                <p>Loading your preferences...</p>
            </div>

            <template v-else>
                <!-- GENERAL SETTINGS TAB -->
                <div v-if="activeTab === 'general'" class="tab-content animate-in">
                    <div class="glass-card" style="max-width: 600px; margin: 0 auto; padding: 2rem;">
                         <div style="text-align: center; margin-bottom: 2rem;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">🛡️</div>
                            <h2 style="font-size: 1.5rem; font-weight: 600; color: #111827; margin-bottom: 0.5rem;">Privacy & Anonymity</h2>
                            <p style="color: #6b7280;">Adjust how sensitive financial data is displayed across the application.</p>
                        </div>

                         <div class="form-group">
                            <label class="form-label">Masking Factor</label>
                            <div class="input-group-flex" style="display: flex; align-items: center; gap: 1rem;">
                                <input 
                                    type="number" 
                                    v-model.number="settingsStore.maskingFactor" 
                                    min="1"
                                    class="form-input" 
                                    placeholder="1"
                                    style="flex: 1;" 
                                />
                                <button @click="saveSettings" class="btn-primary-glow">Save</button>
                            </div>
                            <span class="input-hint">Divide all amounts by this number (e.g., 1, 10, 100)</span>
                        </div>

                        <div class="info-box" style="background: #f3f4f6; padding: 1rem; border-radius: 0.5rem; margin-top: 1.5rem; display: flex; align-items: start; gap: 0.75rem;">
                            <span style="font-size: 1.25rem;">💡</span>
                            <div>
                                <h4 style="font-weight: 600; color: #374151; margin-bottom: 0.25rem;">How it works</h4>
                                <p style="font-size: 0.875rem; color: #4b5563; line-height: 1.5;">
                                    If you set the factor to <strong>10</strong>, a transaction of <strong>₹10,000</strong> will be displayed as <strong>₹1,000</strong>. 
                                    This allows you to share your screen or demo the app without revealing actual values.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ACCOUNTS TAB -->
                <div v-if="activeTab === 'accounts'" class="tab-content animate-in">
                    <!-- Account Summary Widgets -->
                    <div class="summary-widgets">
                        <div class="mini-stat-card glass h-glow-primary">
                            <div class="stat-top">
                                <span class="stat-label">Total Liquid Wealth</span>
                                <span class="stat-icon-bg gray">⚖️</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(accountMetrics.total) }}</div>
                        </div>
                        <div class="mini-stat-card glass h-glow-success">
                            <div class="stat-top">
                                <span class="stat-label">Bank Balance</span>
                                <span class="stat-icon-bg green">🏦</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(accountMetrics.bank) }}</div>
                        </div>
                        <div class="mini-stat-card glass h-glow-warning">
                            <div class="stat-top">
                                <span class="stat-label">Cash on Hand</span>
                                <span class="stat-icon-bg yellow">💵</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(accountMetrics.cash) }}</div>
                        </div>
                        <div class="mini-stat-card glass h-glow-danger">
                            <div class="stat-top">
                                <span class="stat-label">Credit Consumed</span>
                                <span class="stat-icon-bg red">💳</span>
                            </div>
                            <div class="stat-value">{{ formatAmount(accountMetrics.credit) }}</div>
                        </div>
                   </div>

                    <!-- Untrusted Accounts -->
                    <div v-if="untrustedAccounts.length > 0" class="alert-section">
                        <h2 class="section-title warning">⚠️ New Detected Accounts</h2>
                        <div class="settings-grid">
                            <div v-for="acc in untrustedAccounts" :key="acc.id" class="glass-card untrusted pulse-border">
                                <div class="card-top">
                                    <div class="card-main">
                                        <div class="card-type-header">
                                            <span class="type-icon">{{ getAccountTypeIcon(acc.type) }}</span>
                                            <span class="card-label">Untrusted Source</span>
                                        </div>
                                        <h3 class="card-name">{{ acc.name }}</h3>
                                    </div>
                                    <div class="card-actions-row">
                                        <button @click="deleteAccountRequest(acc)" class="btn-icon-circle danger-subtle">🗑️</button>
                                        <button @click="openEditAccountModal(acc, true)" class="btn-verify">Verify</button>
                                    </div>
                                </div>
                                <div class="card-bottom">
                                    <div v-if="acc.type === 'CREDIT_CARD'" class="credit-mini-info">
                                        <span class="card-balance">{{ formatAmount(acc.balance || 0) }} used</span>
                                        <span v-if="acc.credit_limit" class="card-meta">{{ formatAmount(acc.credit_limit - (acc.balance || 0)) }} left</span>
                                    </div>
                                    <span v-else class="card-balance">{{ formatAmount(acc.balance || 0) }}</span>
                                    <span class="card-meta">Auto-Detected</span>
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
                                        <span class="type-icon">{{ getAccountTypeIcon(acc.type) }}</span>
                                        <span class="card-label">{{ getAccountTypeLabel(acc.type) }}</span>
                                    </div>
                                    <h3 class="card-name">{{ acc.name }}</h3>
                                </div>
                                <div class="card-actions">
                                    <button @click="openEditAccountModal(acc)" class="btn-icon-circle">✏️</button>
                                    <button @click="deleteAccountRequest(acc)" class="btn-icon-circle danger-subtle">🗑️</button>
                                </div>
                            </div>
                            <div class="card-bottom">
                                <div v-if="acc.type === 'CREDIT_CARD'" class="credit-mini-info">
                                    <span class="card-balance">{{ formatAmount(acc.balance || 0) }} <span class="card-sub-label">used</span></span>
                                    <span v-if="acc.credit_limit" class="card-available-info">{{ formatAmount(acc.credit_limit - (acc.balance || 0)) }} <span class="card-sub-label">left</span></span>
                                </div>
                                <span v-else class="card-balance">{{ formatAmount(acc.balance || 0) }}</span>
                                    <div class="card-pills">
                                        <span class="owner-badge">
                                            {{ resolveOwnerAvatar(acc) }} {{ resolveOwnerName(acc) }}
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

                <!-- EMAILS TAB -->
                <div v-if="activeTab === 'emails'" class="tab-content animate-in">
                <div v-if="syncStatus && syncStatus.status !== 'running'" :class="['global-sync-alert', syncStatus.status]">
                    <div class="alert-content">
                        {{ syncStatus.status === 'completed' ? '✅ Sync successful' : '❌ Sync failed' }}: 
                        {{ syncStatus.message || `${syncStatus.stats?.processed} transactions ingested.` }}
                    </div>
                    <button @click="syncStatus = null" class="btn-close-alert">✕</button>
                </div>

                <div class="settings-grid">
                    <div v-for="config in emailConfigs" :key="config.id" class="glass-card email-config">
                        <div class="card-top">
                            <div class="card-main">
                                <div class="card-type-header">
                                    <span class="type-dot" :class="config.is_active ? 'green' : 'gray'"></span>
                                    <span class="card-label">{{ config.imap_server }}</span>
                                    <span v-if="config.auto_sync_enabled" class="badge-mini ml-2">Auto-Sync</span>
                                </div>
                                <h3 class="card-name">{{ config.email }}</h3>
                            </div>
                            <div class="card-actions-row">
                                <button @click="openHistoryModal(config)" class="btn-icon-circle" title="View Sync History">📜</button>
                                <button @click="openEditEmailModal(config)" class="btn-icon-circle" title="Edit Configuration">✏️</button>
                            </div>
                        </div>
                        <div class="card-bottom">
                            <span class="card-balance">{{ config.folder }}</span>
                            <!-- Loading State for specific card -->
                            <span v-if="syncStatus && syncStatus.configId === config.id && syncStatus.status === 'running'" class="sync-spinner">🔄 Syncing...</span>
                            <span v-else-if="config.last_sync_at" class="card-meta">
                                Synced: {{ formatDate(config.last_sync_at).day }} {{ formatDate(config.last_sync_at).meta }}
                            </span>
                            <span v-else class="card-meta">Never synced</span>
                        </div>
                        <div class="card-actions">
                            <button @click="handleSync(config.id)" class="btn-verify width-full" :disabled="syncStatus && syncStatus.status === 'running'">
                                {{ (syncStatus && syncStatus.configId === config.id && syncStatus.status === 'running') ? 'Syncing...' : 'Sync Now' }}
                            </button>
                        </div>
                    </div>

                    <div v-if="emailConfigs.length === 0" class="empty-card" @click="showEmailModal = true">
                        <span class="empty-plus">+</span>
                        <p>Link a bank email account</p>
                    </div>
                </div>
            </div>

            <!-- FAMILY TAB -->
            <div v-if="activeTab === 'tenants'" class="tab-content animate-in">
                <!-- Family Hero -->
                <div class="family-hero mb-8" v-if="tenants.length > 0">
                    <div class="fh-main">
                        <div class="fh-avatar-stack">
                           <div v-for="m in familyMembers.slice(0,3)" :key="m.id" class="stack-avatar">
                               {{ m.avatar || '👤' }}
                           </div>
                        </div>
                        <div class="fh-text">
                            <h2 class="fh-title">
                                {{ tenants[0].name }} 
                                <button @click="openRenameTenantModal(tenants[0])" class="btn-icon-subtle" title="Rename Family">✏️</button>
                            </h2>
                            <p class="fh-subtitle">{{ familyMembers.length }} Members • {{ accounts.length }} Accounts Tracked</p>
                        </div>
                    </div>
                </div>

                <div class="settings-grid">
                    <div v-for="member in familyMembers" :key="member.id" class="glass-card member-profile-card">
                        <button @click="openEditMemberModal(member)" class="edit-profile-btn" title="Edit Profile">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
                            </svg>
                        </button>
                        
                        <div class="profile-header">
                            <div class="profile-avatar-wrapper">
                                <div class="gradient-avatar" :class="getRoleColorClass(member.role)">
                                    {{ member.avatar || '👤' }}
                                </div>
                                <div v-if="currentUser && currentUser.id === member.id" class="you-indicator" title="That's You!">
                                    👋
                                </div>
                            </div>
                            <h3 class="profile-name">{{ member.full_name || 'Anonymous' }}</h3>
                            <p class="profile-email">{{ member.email }}</p>
                            <div class="role-pill" :class="member.role.toLowerCase()">
                                {{ getRoleIcon(member.role) }} {{ member.role }}
                            </div>
                        </div>

                        <div class="profile-stats">
                            <div class="stat-item">
                                <span class="stat-val">{{ getMemberAccountCount(member.id) }}</span>
                                <span class="stat-lbl">Accounts</span>
                            </div>
                            <!-- Future: Add 'Txns' or 'Spent' here -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- RULES TAB -->
            <div v-if="activeTab === 'rules'" class="tab-content animate-in">
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
            <div v-if="activeTab === 'categories'" class="tab-content animate-in">
                <div class="settings-grid">
                    <div v-for="cat in categories" :key="cat.id" class="glass-card category" :style="{ borderLeft: `4px solid ${cat.color || '#e5e7eb'}` }">
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
            <!-- AI INTEGRATION TAB (RE-DESIGNED) -->
            <div v-if="activeTab === 'ai'" class="tab-content animate-in">
                <div class="ai-layout max-w-7xl mx-auto">
                    <!-- Left Column: Config -->
                    <div class="ai-config-section">
                        <!-- AI Status Hero -->
                        <div class="ai-toggle-banner">
                            <div class="ai-toggle-info">
                                <h3>AI Transaction Safety Net</h3>
                                <p>Automatically extract details when static rules fail.</p>
                            </div>
                            <label class="switch-premium">
                                <input type="checkbox" v-model="aiForm.is_enabled">
                                <span class="slider-premium"></span>
                            </label>
                        </div>

                        <div class="ai-card">
                            <div class="ai-card-header">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-600"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                                <h4 class="ai-card-title">LLM Configuration</h4>
                            </div>
                            <div class="ai-card-body">
                                <form @submit.prevent="saveAiSettings" class="space-y-6">
                                    <div class="form-row">
                                        <div class="ai-input-group half">
                                            <label class="ai-input-label">AI Provider</label>
                                            <CustomSelect 
                                                v-model="aiForm.provider" 
                                                :options="[{ label: 'Google Gemini', value: 'gemini' }]"
                                            />
                                        </div>
                                        <div class="ai-input-group half">
                                            <label class="ai-input-label">Model Selection</label>
                                            <div class="flex gap-2">
                                                <CustomSelect 
                                                    v-model="aiForm.model_name" 
                                                    :options="aiModels"
                                                    class="flex-1"
                                                />
                                                <button type="button" @click="fetchAiModels" class="btn-icon-circle" title="Refresh Models">🔄</button>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="ai-input-group">
                                        <label class="ai-input-label">Secure API Key</label>
                                        <input 
                                            type="password" 
                                            v-model="aiForm.api_key" 
                                            class="form-input" 
                                            :placeholder="aiForm.has_api_key ? '••••••••••••••••' : 'Paste API key...'" 
                                        />
                                        <div class="ai-input-helper">
                                            Keys are encrypted at rest. Get your key from the 
                                            <a href="https://aistudio.google.com/app/apikey" target="_blank" class="text-indigo-600 font-bold">Google AI Studio</a>.
                                        </div>
                                    </div>

                                    <div class="ai-input-group">
                                        <div class="flex justify-between items-center mb-2">
                                            <label class="ai-input-label m-0">System Instruction</label>
                                            <button type="button" class="text-xs text-indigo-600 font-bold" @click="aiForm.prompts.parsing = 'Extract transaction details...'">Reset to Default</button>
                                        </div>
                                        <textarea 
                                            v-model="aiForm.prompts.parsing" 
                                            class="form-input font-mono text-xs" 
                                            rows="4"
                                        ></textarea>
                                        <p class="ai-input-helper">Define how the AI should structure the extracted JSON data.</p>
                                    </div>

                                    <div class="flex justify-end pt-4 border-t border-gray-50">
                                        <button type="submit" class="ai-btn-primary">
                                            Save Preferences
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Right Column: Playground -->
                    <div class="ai-playground">
                        <div class="ai-card">
                            <div class="ai-card-header">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-amber-500"><path d="M12 2L2 7l10 5l10-5l-10-5zM2 17l10 5l10-5M2 12l10 5l10-5"/></svg>
                                <h4 class="ai-card-title">Test Playground</h4>
                            </div>
                            <div class="ai-card-body">
                                <p class="text-[11px] text-muted mb-4 leading-relaxed">
                                    Paste a message below to see how the current configuration parses it.
                                </p>
                                
                                <textarea 
                                    v-model="aiTestMessage" 
                                    class="form-input text-xs mb-4 bg-gray-50 border-dashed" 
                                    rows="3" 
                                    placeholder="e.g. Spent Rs 500 at Amazon..."
                                ></textarea>
                                
                                <button 
                                    @click="testAi" 
                                    class="btn-verify width-full mb-6"
                                    :disabled="aiTesting"
                                >
                                    {{ aiTesting ? 'Analyzing...' : 'Test Extraction' }}
                                </button>

                                <div class="console-box">
                                    <div class="console-header">
                                        <div class="flex gap-1">
                                            <span class="console-dot green"></span>
                                            <span class="console-dot yellow"></span>
                                        </div>
                                        <span>DEBUG CONSOLE</span>
                                    </div>
                                    <div class="ai-console">
                                        <div v-if="!aiTestResult && !aiTesting" class="text-slate-500 italic">
                                            Waiting for data...
                                        </div>
                                        <div v-if="aiTesting" class="animate-pulse text-indigo-400">
                                            > Initializing Gemini provider...
                                            <br>> Sending payload...
                                        </div>
                                        <pre v-if="aiTestResult">{{ JSON.stringify(aiTestResult.data || aiTestResult.message, null, 2) }}</pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            </template>
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
                    

                    <div class="form-row">
                        <div class="form-group half">
                            <label class="form-label">Type</label>
                            <CustomSelect 
                                v-model="newAccount.type"
                                :options="[
                                    { label: '🏦 Bank Account', value: 'BANK' },
                                    { label: '💳 Credit Card', value: 'CREDIT_CARD' },
                                    { label: '💸 Loan / EMIs', value: 'LOAN' },
                                    { label: '👛 Wallet / Cash', value: 'WALLET' },
                                    { label: '📈 Investment', value: 'INVESTMENT' }
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
                        <label class="form-label">Account Owner</label>
                        <CustomSelect 
                            v-model="newAccount.owner_id" 
                            :options="familyMembers.map(m => ({ label: m.full_name || m.email, value: m.id }))"
                            placeholder="Select Owner"
                        />
                    </div>

                    <div class="form-row">
                        <div class="form-group" :class="newAccount.type === 'CREDIT_CARD' ? 'half' : 'full'">
                            <label class="form-label">{{ newAccount.type === 'CREDIT_CARD' ? 'Consumed Limit' : 'Current Balance' }}</label>
                            <input type="number" v-model.number="newAccount.balance" class="form-input" step="0.01" />
                        </div>
                        <div v-if="newAccount.type === 'CREDIT_CARD'" class="form-group half">
                            <label class="form-label">Total Credit Limit</label>
                            <input type="number" v-model.number="newAccount.credit_limit" class="form-input" step="0.01" placeholder="e.g. 100000" />
                        </div>
                    </div>

                    <div class="setting-toggle-row">
                        <div class="toggle-label">
                            <span class="font-medium">Verified Account</span>
                            <span class="text-xs text-muted">Trust transactions from this source</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="newAccount.is_verified">
                            <span class="slider round"></span>
                        </label>
                    </div>

                    <div class="modal-footer">
                        <button type="button" @click="showAccountModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Changes</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Email Config Modal -->
        <div v-if="showEmailModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ editingEmailConfig ? 'Edit Email Config' : 'Link Email Account' }}</h2>
                    <button class="btn-icon-circle" @click="showEmailModal = false">✕</button>
                </div>
                
                <form @submit.prevent="saveEmailConfig" class="form-compact">
                    <div class="form-group">
                        <label class="form-label">Email Address</label>
                        <input v-model="emailForm.email" class="form-input" required placeholder="name@gmail.com" />
                    </div>
                    <div class="form-group">
                        <label class="form-label">Gmail App Password</label>
                        <input type="password" v-model="emailForm.password" class="form-input" required placeholder="•••• •••• •••• ••••" />
                        <div class="info-note mt-2">
                            ℹ️ Use a generated <strong>App Password</strong>, not your main Google login.
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">IMAP Server</label>
                        <input v-model="emailForm.host" class="form-input" required placeholder="imap.gmail.com" />
                    </div>
                    <div class="form-group">
                        <label class="form-label">IMAP Folder</label>
                        <input v-model="emailForm.folder" class="form-input" placeholder="INBOX" />
                    </div>

                    <div class="setting-toggle-row">
                        <div class="toggle-label">
                            <span class="font-medium">Auto-Sync</span>
                            <span class="text-xs text-muted">Check for emails every 15 mins</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="emailForm.auto_sync">
                            <span class="slider round"></span>
                        </label>
                    </div>
                    
                    <div class="modal-footer flex-between">
                        <button type="button" @click="deleteEmailConfig(editingEmailConfig)" v-if="editingEmailConfig" class="btn-text-danger">
                            🗑 Remove
                        </button>
                        <div style="display: flex; gap: 0.5rem; margin-left: 0.5rem; align-items: center;">
                            <button type="button" @click="rewindSync(3)" v-if="editingEmailConfig" class="btn-text-warning" style="font-size: 0.8rem; border:none; background:rgba(245, 158, 11, 0.1); padding: 4px 8px; border-radius: 4px; cursor:pointer;" title="Rescan last 3 hours">
                                ⏪ Rewind 3h
                            </button>
                            <button type="button" @click="resetSyncHistory" v-if="editingEmailConfig" class="btn-text-danger" style="font-size: 0.8rem; border:none; background:none; cursor:pointer;" title="Force deep scan of ALL history">
                                🔄 Full Reset
                            </button>
                        </div>
                        <div style="display: flex; gap: 1rem; margin-left: auto;">
                            <button type="button" @click="showEmailModal = false" class="btn-secondary">Cancel</button>
                            <button type="submit" class="btn-primary-glow">
                                {{ editingEmailConfig ? 'Update Config' : 'Connect Account' }}
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <!-- Sync History Modal -->
        <div v-if="showHistoryModal" class="modal-overlay-global">
            <div class="modal-global modal-lg glass">
                <div class="modal-header">
                    <h2 class="modal-title">Sync History</h2>
                    <button class="btn-icon-circle" @click="showHistoryModal = false">✕</button>
                </div>
                
                <div class="history-list">
                    <div v-if="syncLogs.length === 0" class="empty-state-small">No logs found.</div>
                    <table v-else class="compact-table">
                        <thead>
                            <tr>
                                <th>Status</th>
                                <th>Time</th>
                                <th>Items</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="log in syncLogs" :key="log.id">
                                <td class="text-center">{{ getLogIcon(log.status) }}</td>
                                <td>{{ formatDateFull(log.started_at) }}</td>
                                <td>{{ log.items_processed || 0 }}</td>
                                <td class="text-muted">{{ log.message }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div class="modal-footer">
                     <button type="button" @click="showHistoryModal = false" class="btn-secondary">Close</button>
                </div>
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
                        <label class="form-label">Icon (Emoji) & Color</label>
                        <div style="display: flex; gap: 1rem;">
                            <input v-model="newCategory.icon" class="form-input emoji-input" required placeholder="🏷️" />
                            <input type="color" v-model="newCategory.color" class="form-input" style="height: 3rem; padding: 0.2rem; width: 100%; cursor: pointer;" />
                        </div>
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
        <!-- Delete Category Confirmation -->
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
        <!-- Delete Account Confirmation -->
        <div v-if="showAccountDeleteConfirm" class="modal-overlay-global">
            <div class="modal-global glass alert max-w-md">
                <div class="modal-icon-header danger">🗑️</div>
                <h2 class="modal-title">Delete Account?</h2>
                <div class="alert-info-box mb-6">
                    <p class="mb-2">You are about to delete <strong>{{ accountToDelete?.name }}</strong>.</p>
                    <p class="text-danger font-bold" v-if="accountTxCount > 0">
                        ⚠️ This will also permanently delete {{ accountTxCount }} transactions.
                    </p>
                    <p v-else class="text-muted">No transactions are currently linked to this account.</p>
                </div>
                <p class="text-xs text-muted mb-6">This action cannot be undone. Are you absolutely sure?</p>
                
                <div class="modal-footer">
                    <button @click="showAccountDeleteConfirm = false" class="btn-secondary" :disabled="isDeletingAccount">Cancel</button>
                    <button @click="confirmAccountDelete" class="btn-danger-glow" :disabled="isDeletingAccount">
                        {{ isDeletingAccount ? 'Deleting...' : 'Yes, Delete Everything' }}
                    </button>
                </div>
            </div>
        </div>


        <!-- Add/Edit Family Member Modal -->
        <div v-if="showMemberModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">{{ isEditingMember ? 'Edit Profile' : 'Add Family Member' }}</h2>
                    <button class="btn-icon-circle" @click="showMemberModal = false">✕</button>
                </div>
                
                <form @submit.prevent="handleMemberSubmit" class="form-compact">
                    <div class="avatar-picker-grid">
                        <div v-for="a in ['👨‍💼', '👩‍💼', '👶', '👴', '👵', '👨‍🎓', '👩‍🎓', '🐶']" 
                             :key="a"
                             class="avatar-option"
                             :class="{ active: memberForm.avatar === a }"
                             @click="memberForm.avatar = a">
                            {{ a }}
                        </div>
                        <input v-model="memberForm.avatar" class="form-input emoji-input-sm" maxlength="2" placeholder="🔍" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Full Name</label>
                        <input v-model="memberForm.full_name" class="form-input" required placeholder="e.g. Sarah Smith" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Email Address</label>
                        <input v-model="memberForm.email" class="form-input" :disabled="isEditingMember" type="email" required placeholder="sarah@example.com" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Password {{ isEditingMember ? '(Leave empty to keep current)' : '' }}</label>
                        <input v-model="memberForm.password" class="form-input" type="password" :required="!isEditingMember" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Role / Permissions</label>
                        <CustomSelect 
                            v-model="memberForm.role" 
                            :options="[
                                { label: 'Admin (See everything)', value: 'OWNER' },
                                { label: 'Adult (Edit access)', value: 'ADULT' },
                                { label: 'Child (Watch only / Restricted)', value: 'CHILD' },
                                { label: 'Guest', value: 'GUEST' }
                            ]"
                        />
                    </div>

                    <div class="modal-footer">
                         <button type="button" @click="showMemberModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">{{ isEditingMember ? 'Save Changes' : 'Add Member' }}</button>
                    </div>
                </form>
            </div>
        </div>
        <!-- Tenant Rename Modal -->
        <div v-if="showTenantModal" class="modal-overlay-global">
            <div class="modal-global glass">
                <div class="modal-header">
                    <h2 class="modal-title">Rename Family Circle</h2>
                    <button class="btn-icon-circle" @click="showTenantModal = false">✕</button>
                </div>
                
                <form @submit.prevent="handleRenameTenant" class="form-compact">
                    <div class="form-group">
                        <label class="form-label">New Family Name</label>
                        <input v-model="tenantForm.name" class="form-input" required placeholder="e.g. The Smiths" />
                    </div>
                    <div class="modal-footer">
                         <button type="button" @click="showTenantModal = false" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary-glow">Save Changes</button>
                    </div>
                </form>
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

.modal-global.modal-lg {
    max-width: 800px; /* Wider */
    width: 90%;
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

/* Modal for Email Config */
.modal-footer-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1.5rem;
}

.global-sync-alert {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
    border-radius: 0.75rem;
    margin-bottom: 1.5rem;
    font-size: 0.875rem;
    font-weight: 600;
}

.global-sync-alert.completed { background: #ecfdf5; color: #059669; }
.global-sync-alert.error { background: #fef2f2; color: #dc2626; }

.btn-close-alert { background: transparent; border: none; cursor: pointer; color: inherit; font-size: 1rem; }

/* Sync Integration Styling */
.sync-integration {
    background: linear-gradient(135deg, white 0%, #f9fafb 100%);
    border: 1px solid #e5e7eb;
}

.sync-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
}

.sync-info h3 {
    font-size: 1rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 0.25rem;
}

.sync-form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
    padding: 1.25rem;
    background: white;
    border-radius: 1rem;
    border: 1px solid #f3f4f6;
}

.form-group.half-v {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.sync-result {
    margin-top: 1.25rem;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    font-size: 0.875rem;
    font-weight: 600;
}

/* Sync History Table */
.compact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.compact-table th {
    text-align: left;
    padding: 0.75rem 0.5rem;
    border-bottom: 1px solid #e5e7eb;
    color: #6b7280;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.compact-table td {
    padding: 0.4rem 0.6rem; /* Reduced padding */
    border-bottom: 1px solid #f3f4f6;
    color: #374151;
    vertical-align: middle;
}

/* Force message column to truncate */
.compact-table td.text-muted {
    max-width: 350px; /* Wider for more details */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Suggestions / Rules Fix */
.glass-card.suggestion .card-top {
    gap: 1rem; /* Ensure space between text and button */
}

/* Prevent text from pushing button out */
.card-main {
    min-width: 0; /* Critical for flex child truncation */
    flex: 1;
    overflow: hidden;
}

.card-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.btn-approve {
    padding: 0.375rem 0.75rem;
    background: #eff6ff;
    color: #4f46e5;
    border: 1px solid #c7d2fe;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0; /* Never shrink the button */
    transition: all 0.2s;
}

.btn-approve:hover {
    background: #4f46e5;
    color: white;
    border-color: #4f46e5;
}

.sync-result.completed {
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #d1fae5;
}

.sync-result.error {
    background: #fef2f2;
    color: #dc2626;
    border: 1px solid #fee2e2;
}

.mt-4 { margin-top: 1.5rem; }
.text-muted { color: #6b7280; font-size: 0.75rem; }

/* Card Specifics */
.glass-card.email-config, .glass-card.tenant-card {
    min-height: 100px;
    justify-content: space-between;
}

.card-actions-row {
    display: flex;
    gap: 0.5rem;
}

.email-config .card-meta {
    font-size: 0.7rem;
    color: #6b7280;
    display: block;
}

.tenant-card .card-name {
    color: #4f46e5;
}

/* Family management */
.mb-8 { margin-bottom: 2rem; }
.section-divider { height: 1px; background: #e5e7eb; margin: 2rem 0; }
/* Member Profile Card */
.member-profile-card {
    position: relative;
    padding: 0 !important; /* Reset standard padding to allow custom layout */
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.member-profile-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.08);
}

.edit-profile-btn {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    width: 2rem; height: 2rem;
    border-radius: 50%;
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(0,0,0,0.05);
    color: #6b7280;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
}
.edit-profile-btn:hover { background: white; color: #4f46e5; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }

.profile-header {
    padding: 2rem 1.5rem 1.5rem;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
}

.profile-avatar-wrapper {
    position: relative;
    margin-bottom: 0.5rem;
}
.gradient-avatar {
    width: 4rem; height: 4rem;
    font-size: 2.25rem;
    background: white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 8px 16px rgba(0,0,0,0.08);
    border: 3px solid white;
}
/* Ring colors for avatar borders */
.gradient-avatar.ring-gold { border-color: #fbbf24; background: linear-gradient(135deg, #fffbeb, #fff); }
.gradient-avatar.ring-blue { border-color: #818cf8; background: linear-gradient(135deg, #eef2ff, #fff); }
.gradient-avatar.ring-green { border-color: #34d399; background: linear-gradient(135deg, #ecfdf5, #fff); }
.gradient-avatar.ring-gray { border-color: #9ca3af; }

.you-indicator {
    position: absolute;
    bottom: -5px; right: -5px;
    background: white;
    border-radius: 50%;
    width: 1.5rem; height: 1.5rem;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border: 1px solid #e5e7eb;
}

.profile-name {
    font-size: 1.125rem;
    font-weight: 700;
    color: #111827;
    margin: 0;
}

.profile-email {
    font-size: 0.8rem;
    color: #6b7280;
    margin: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.role-pill {
    margin-top: 0.5rem;
}

.profile-stats {
    width: 100%;
    padding: 1rem 1.5rem;
    background: #f9fafb;
    border-top: 1px solid #f3f4f6;
    display: flex;
    justify-content: center; /* Center since only 1 stat for now */
    gap: 1rem;
}

.stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
}
.stat-val { font-size: 1.125rem; font-weight: 700; color: #111827; line-height: 1; }
.stat-lbl { font-size: 0.65rem; text-transform: uppercase; font-weight: 600; color: #9ca3af; letter-spacing: 0.05em; margin-top: 0.25rem; }
.gradient-avatar.ring-blue { border-color: #4f46e5; background: linear-gradient(135deg, #eef2ff, #fff); }
.gradient-avatar.ring-green { border-color: #10b981; background: linear-gradient(135deg, #ecfdf5, #fff); }
.gradient-avatar.ring-gray { border-color: #9ca3af; }


.member-details {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    flex: 1;
}

.member-header-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.member-name {
    font-size: 1.125rem;
    font-weight: 700;
    color: #111827;
    margin: 0;
}

.role-pill {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border-radius: 99px;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
    gap: 0.25rem;
}
.role-pill.owner { background: #fffbeb; color: #b45309; border: 1px solid #fcd34d; }
.role-pill.adult { background: #eef2ff; color: #4338ca; border: 1px solid #c7d2fe; }
.role-pill.child { background: #ecfdf5; color: #15803d; border: 1px solid #86efac; }
.role-pill.guest { background: #f3f4f6; color: #4b5563; }

.meta-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 0.25rem;
}

.account-count-badge {
    font-size: 0.75rem;
    font-weight: 500;
    color: #6b7280;
    background: #f9fafb;
    padding: 0.1rem 0.5rem;
    border-radius: 6px;
    border: 1px solid #e5e7eb;
}

.btn-icon-soft {
    width: 2.25rem; height: 2.25rem;
    border-radius: 50%;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 1rem;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s;
}
.btn-icon-soft:hover { background: #f3f4f6; }

/* Avatar Picker */
.avatar-picker-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.5rem;
}

.avatar-option {
    font-size: 1.5rem;
    padding: 0.75rem;
    background: #f9fafb;
    border: 2px solid transparent;
    border-radius: 0.75rem;
    cursor: pointer;
    text-align: center;
    transition: all 0.2s;
}

.avatar-option:hover { background: #f3f4f6; }
.avatar-option.active { border-color: #4f46e5; background: #eef2ff; }

.emoji-input-sm {
    font-size: 1.125rem;
    text-align: center;
}

/* Family Hero */
.family-hero {
    display: flex;
    align-items: center;
    background: linear-gradient(to right, #ffffff, #f9fafb);
    padding: 2rem;
    border-radius: 1.5rem;
    border: 1px solid #e5e7eb;
}

.fh-main {
    display: flex;
    align-items: center;
    gap: 1.5rem;
}

.fh-avatar-stack {
    display: flex;
    padding-left: 0.5rem;
}
.stack-avatar {
    width: 3rem; height: 3rem;
    border-radius: 50%;
    background: white;
    border: 3px solid #fff;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem;
    margin-left: -1rem;
    position: relative;
    z-index: 1;
}

.fh-text {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.fh-title {
    font-size: 2rem;
    font-weight: 800;
    color: #111827;
    margin: 0;
    line-height: 1.1;
    display: flex; align-items: center; gap: 0.5rem;
}

.fh-subtitle {
    font-size: 0.95rem;
    color: #6b7280;
    font-weight: 500;
}

.btn-icon-subtle {
    font-size: 1rem;
    opacity: 0.3;
    transition: opacity 0.2s;
    background: none; border: none; cursor: pointer;
}
.btn-icon-subtle:hover { opacity: 1; }

.current-user-badge {
    font-size: 0.75rem;
    color: #4f46e5;
    background: #eef2ff;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    vertical-align: middle;
}

/* Polished Email Modal Styles */
.setting-toggle-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: #f9fafb;
    border-radius: 0.75rem;
    border: 1px solid #f3f4f6;
    margin-bottom: 1.5rem;
}
.toggle-label {
    display: flex;
    flex-direction: column;
}
/* Toggle Switch */
.switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
}
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: #ccc;
    transition: .4s;
    border-radius: 34px;
}
.slider:before {
    position: absolute;
    content: "";
    height: 18px; width: 18px;
    left: 3px; bottom: 3px;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
}
input:checked + .slider { background-color: #4f46e5; }
input:checked + .slider:before { transform: translateX(20px); }

.info-note {
    font-size: 0.75rem;
    color: #1d4ed8;
    background: #eff6ff;
    border: 1px solid #dbeafe;
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    line-height: 1.4;
}

.btn-text-danger {
    background: none; border: none;
    color: #dc2626;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.5rem;
    display: flex; align-items: center; gap: 0.25rem;
    transition: opacity 0.2s;
}
.btn-text-danger:hover { opacity: 0.8; background: #fef2f2; border-radius: 0.5rem; }

.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}
.btn-icon-circle.danger-subtle {
    color: #ef4444;
}
.btn-icon-circle.danger-subtle:hover {
    background: #fef2f2;
}

.modal-icon-header.danger {
    font-size: 3rem;
    margin-bottom: 1rem;
    text-align: center;
}

.alert-info-box {
    background: #fdf2f2;
    border: 1px solid #fecaca;
    border-radius: 0.75rem;
    padding: 1rem;
}

.btn-danger-glow {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    border: none;
    border-radius: 0.625rem;
    padding: 0.5rem 1rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
    transition: all 0.2s;
}

.btn-danger-glow:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(239, 68, 68, 0.3);
}

.btn-danger-glow:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}
/* AI Settings Professional Redesign */
.premium-p-8 { padding: 2.5rem; }
.ai-layout { display: grid; grid-template-columns: 1fr 340px; gap: 2.5rem; align-items: start; }
@media (max-width: 1024px) { .ai-layout { grid-template-columns: 1fr; } }

.ai-card { background: white; border-radius: 1.25rem; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); overflow: hidden; }
.ai-card-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid #f3f4f6; display: flex; align-items: center; gap: 0.75rem; background: #fafafa; }
.ai-card-title { font-size: 0.95rem; font-weight: 700; color: #1f2937; margin: 0; }
.ai-card-body { padding: 1.5rem; }

.ai-toggle-banner { 
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); 
    padding: 1.5rem; border-radius: 1rem; color: white; 
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 2rem; box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.2);
}
.ai-toggle-info h3 { margin: 0; font-size: 1.1rem; font-weight: 700; }
.ai-toggle-info p { margin: 0.25rem 0 0 0; font-size: 0.85rem; opacity: 0.9; }

/* Account Card Enhancements */
.type-icon {
    font-size: 1.125rem;
    margin-right: 0.5rem;
}

.credit-mini-info {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
}

.card-available-info {
    font-size: 0.75rem;
    font-weight: 600;
    color: #059669;
}

.card-sub-label {
    font-size: 0.65rem;
    font-weight: 500;
    color: #9ca3af;
    text-transform: uppercase;
}

.ai-input-group { margin-bottom: 1.5rem; }
.ai-input-label { display: block; font-size: 0.8rem; font-weight: 600; color: #4b5563; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.025em; }
.ai-input-helper { font-size: 0.75rem; color: #6b7280; margin-top: 0.5rem; line-height: 1.4; }

.ai-playground { position: sticky; top: 2rem; }
.ai-console { 
    background: #0f172a; border-radius: 0.75rem; padding: 1rem; 
    font-family: 'JetBrains Mono', 'Fira Code', monospace; 
    color: #e2e8f0; font-size: 0.75rem; min-height: 200px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
}
.console-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid #1e293b; color: #94a3b8; }
.console-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.console-dot.green { background: #10b981; }
.console-dot.yellow { background: #f59e0b; }

.badge-mini.primary { background: rgba(79, 70, 229, 0.1); color: #4f46e5; border: 1px solid rgba(79, 70, 229, 0.2); font-weight: 700; }

/* Switch Redesign */
.switch-premium { position: relative; display: inline-block; width: 50px; height: 26px; }
.switch-premium input { opacity: 0; width: 0; height: 0; }
.slider-premium { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255,255,255,0.3); transition: .4s; border-radius: 34px; }
.slider-premium:before { position: absolute; content: ""; height: 20px; width: 20px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
input:checked + .slider-premium { background-color: rgba(255,255,255,0.5); }
input:checked + .slider-premium:before { transform: translateX(24px); }

.ai-btn-primary { 
    background: #4f46e5; color: white; border: none; padding: 0.75rem 1.5rem; 
    border-radius: 0.75rem; font-weight: 700; cursor: pointer; transition: all 0.2s;
    box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);
}
.ai-btn-primary:hover { transform: translateY(-1px); background: #4338ca; box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3); }

</style>
