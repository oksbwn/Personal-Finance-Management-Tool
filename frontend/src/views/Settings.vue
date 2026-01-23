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

const showAccountModal = ref(false)
const editingAccountId = ref<string | null>(null)
const newAccount = ref({
    name: '',
    type: 'BANK',
    currency: 'INR',
    account_mask: '',
    balance: 0,
    credit_limit: null as number | null,
    billing_day: null as number | null,
    due_day: null as number | null,
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
    avatar: '👨‍💼',
    dob: '',
    pan_number: ''
})

const showPan = ref(false)

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
            notify.info("AI test failed")
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
        billing_day: null,
        due_day: null,
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
        billing_day: account.billing_day,
        due_day: account.due_day,
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
            credit_limit: newAccount.value.type === 'CREDIT_CARD' ? Number(newAccount.value.credit_limit) : null,
            billing_day: (newAccount.value.type === 'CREDIT_CARD' && newAccount.value.billing_day) ? Number(newAccount.value.billing_day) : null,
            due_day: (newAccount.value.type === 'CREDIT_CARD' && newAccount.value.due_day) ? Number(newAccount.value.due_day) : null
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
    auto_sync: false,
    user_id: null as string | null,
    last_sync_at: '' as string // For custom date/time setting
})

async function saveEmailConfig() {
    try {
        const payload: any = {
            email: emailForm.value.email,
            password: emailForm.value.password,
            imap_server: emailForm.value.host,
            folder: emailForm.value.folder,
            auto_sync_enabled: emailForm.value.auto_sync,
            user_id: emailForm.value.user_id
        }

        if (emailForm.value.last_sync_at) {
            payload.last_sync_at = new Date(emailForm.value.last_sync_at).toISOString()
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
        emailForm.value = { email: '', password: '', host: 'imap.gmail.com', folder: 'INBOX', auto_sync: false, user_id: null, last_sync_at: '' }
        fetchData()
    } catch (e) {
        notify.error("Failed to save email config")
    }
}


function openEditEmailModal(config: any) {
    emailForm.value = { 
        email: config.email, 
        password: config.password, 
        host: config.imap_server, 
        folder: config.folder,
        auto_sync: config.auto_sync_enabled || false,
        user_id: config.user_id || null,
        last_sync_at: config.last_sync_at ? new Date(config.last_sync_at).toISOString().slice(0, 16) : ''
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
    if (!dateStr) return { day: 'N/A', meta: '' }
    const d = new Date(dateStr)
    return {
        day: d.toLocaleDateString(),
        meta: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
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
        avatar: '👨‍💼',
        dob: '',
        pan_number: ''
    }
    showPan.value = false
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
        avatar: member.avatar || '👤',
        dob: member.dob || '',
        pan_number: member.pan_number || ''
    }
    showPan.value = false
    showMemberModal.value = true
}

async function handleMemberSubmit() {
    try {
        if (isEditingMember.value) {
            await financeApi.updateUser(memberForm.value.id, {
                full_name: memberForm.value.full_name,
                avatar: memberForm.value.avatar,
                role: memberForm.value.role,
                dob: memberForm.value.dob || undefined,
                pan_number: memberForm.value.pan_number || undefined,
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
                    <!-- All tabs now have inline search and add cards -->
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

                    <!-- Untrusted Accounts (Premium Style) -->
                    <div v-if="untrustedAccounts.length > 0" class="alert-section mb-8">
                        <div class="header-with-badge match-header mb-4">
                            <h3 style="margin: 0; font-size: 1rem; font-weight: 700; color: #b45309;">⚠️ New Detected Accounts</h3>
                            <span class="pulse-status-badge" style="background: #fffbeb; color: #b45309;">{{ untrustedAccounts.length }} Action Needed</span>
                        </div>
                        
                        <div class="settings-grid">
                            <div v-for="acc in untrustedAccounts" :key="acc.id" class="glass-card account-card-premium untrusted-card">
                                <div class="acc-card-top">
                                    <div class="acc-icon-wrapper" :class="acc.type.toLowerCase()">
                                        {{ getAccountTypeIcon(acc.type) }}
                                    </div>
                                    <div class="acc-actions" style="gap: 0.5rem;">
                                        <button @click="openEditAccountModal(acc, true)" class="btn-icon-subtle success" title="Verify Account">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                                <path d="M20 6L9 17l-5-5"/>
                                            </svg>
                                        </button>
                                        <button @click="deleteAccountRequest(acc)" class="btn-icon-subtle danger" title="Reject / Remove">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="M18 6L6 18M6 6l12 12"/>
                                            </svg>
                                        </button>
                                    </div>
                                </div>

                                <div class="acc-card-main">
                                    <div class="acc-label-row">
                                        <span class="acc-type">{{ getAccountTypeLabel(acc.type) }}</span>
                                        <span class="status-badge-mini inactive">Untrusted</span>
                                    </div>
                                    <h3 class="acc-name">{{ acc.name }}</h3>
                                </div>

                                <div class="acc-card-footer">
                                    <div class="acc-balance-group">
                                        <span class="acc-balance-label">Balance</span>
                                        <span class="acc-balance-val">{{ formatAmount(acc.balance || 0) }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Verified Accounts Control Bar (Search Left, Title Right) -->
                    <div class="account-control-bar mt-8 mb-6">
                        <!-- Search on Left -->
                        <div class="search-bar-premium no-margin" style="flex: 1; max-width: 300px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
                                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                            </svg>
                            <input 
                                type="text" 
                                v-model="searchQuery" 
                                placeholder="Search accounts..." 
                                class="search-input"
                            >
                        </div>

                         <!-- Title on Right -->
                         <div class="header-with-badge" style="margin-left: auto; display: flex; align-items: center; gap: 0.75rem;">
                            <h3 style="margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-main); white-space: nowrap;">Tracked Accounts</h3>
                            <span class="pulse-status-badge" style="background: #ecfdf5; color: #047857;">{{ verifiedAccounts.length }} Active</span>
                         </div>
                    </div>

                    <!-- Verified Accounts Grid -->
                    <div class="settings-grid">
                        <div v-for="acc in verifiedAccounts" :key="acc.id" class="glass-card account-card-premium" :class="{'verified-highlight': acc.is_verified}" @click="openEditAccountModal(acc)">
                            <div class="acc-card-top">
                                <div class="acc-icon-wrapper" :class="acc.type.toLowerCase()">
                                    {{ getAccountTypeIcon(acc.type) }}
                                </div>
                                <div class="acc-actions">
                                    <!-- Edit Icon replaced button -->
                                    <button class="btn-icon-subtle" title="Edit Options">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                        </svg>
                                    </button>
                                </div>
                            </div>

                            <div class="acc-card-main">
                                <h3 class="acc-name">{{ acc.name }}</h3>
                                <div class="acc-meta">
                                    <span class="acc-type">{{ getAccountTypeLabel(acc.type) }}</span>
                                    <span v-if="acc.account_mask" class="acc-mask">••{{ acc.account_mask }}</span>
                                </div>
                                <div class="acc-owner-row mt-3">
                                    <div class="owner-pill">
                                        <span class="owner-avatar-xs">{{ resolveOwnerAvatar(acc) }}</span>
                                        <span class="owner-name-xs">{{ resolveOwnerName(acc) }}</span>
                                    </div>
                                </div>
                            </div>

                            <div class="acc-card-footer">
                                <div class="acc-balance-group">
                                    <span class="acc-balance-label">Current Balance</span>
                                    <span class="acc-balance-val" :class="{'text-red': Number(acc.balance) < 0 && acc.type !== 'CREDIT_CARD'}">
                                        {{ formatAmount(Math.abs(Number(acc.balance || 0)), acc.currency) }}
                                        <span v-if="acc.type === 'CREDIT_CARD'" class="balance-tag">used</span>
                                    </span>
                                </div>
                                
                                <div v-if="acc.type === 'CREDIT_CARD' && acc.credit_limit" class="acc-limit-group">
                                    <div class="limit-bar-bg">
                                        <div class="limit-bar-fill" :style="{ width: Math.min(((Math.abs(Number(acc.balance || 0))) / Number(acc.credit_limit)) * 100, 100) + '%' }"></div>
                                    </div>
                                    <span class="limit-text">{{ Math.round((Math.abs(Number(acc.balance || 0)) / Number(acc.credit_limit)) * 100) }}% utilized</span>
                                </div>
                            </div>
                        </div>

                        <!-- Add New Card (Empty State) -->
                        <div v-if="!searchQuery" class="glass-card add-account-card" @click="openCreateAccountModal">
                            <div class="add-icon-circle">+</div>
                            <span>Add New Account</span>
                        </div>
                    </div>
                    
                    <div v-if="verifiedAccounts.length === 0 && searchQuery" class="empty-placeholder">
                        <p>No accounts match "{{ searchQuery }}"</p>
                    </div>
                </div>



                <!-- EMAILS TAB - PREMIUM REDESIGN -->
                <div v-if="activeTab === 'emails'" class="tab-content animate-in">
                    <!-- Search Bar -->
                    <div class="account-control-bar mb-6">
                        <div class="search-bar-premium no-margin" style="flex: 1; max-width: 300px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
                                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                            </svg>
                            <input 
                                type="text" 
                                v-model="searchQuery" 
                                placeholder="Search email accounts..." 
                                class="search-input"
                            >
                        </div>
                        <div class="header-with-badge" style="margin-left: auto; display: flex; align-items: center; gap: 0.75rem;">
                            <h3 style="margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-main); white-space: nowrap;">Email Accounts</h3>
                            <span class="pulse-status-badge" style="background: #ecfdf5; color: #047857;">{{ emailConfigs.length }} Total</span>
                        </div>
                    </div>

                <div v-if="syncStatus && syncStatus.status !== 'running'" :class="['sync-alert-premium', syncStatus.status]">
                    <div class="alert-icon">
                        {{ syncStatus.status === 'completed' ? '✅' : '❌' }}
                    </div>
                    <div class="alert-body">
                        <strong>{{ syncStatus.status === 'completed' ? 'Sync Complete' : 'Sync Failed' }}</strong>
                        <p>{{ syncStatus.message || `${syncStatus.stats?.processed} transactions processed.` }}</p>
                    </div>
                    <button @click="syncStatus = null" class="alert-close">✕</button>
                </div>

                <div class="email-grid">
                    <div v-for="config in emailConfigs" :key="config.id" class="email-card-premium">
                        <!-- Status Indicator Stripe -->
                        <div class="status-stripe" :class="{
                            'active': config.is_active,
                            'inactive': !config.is_active,
                            'auto-sync': config.auto_sync_enabled
                        }"></div>

                        <!-- Card Header -->
                        <div class="email-card-header">
                            <div class="email-info">
                                <div class="email-status-row">
                                    <div class="pulse-dot" :class="config.is_active ? 'active' : 'inactive'"></div>
                                    <span class="server-label">{{ config.imap_server }}</span>
                                    <span v-if="config.auto_sync_enabled" class="auto-sync-badge">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 12a9 9 0 11-6.219-8.56"/>
                                        </svg>
                                        Auto
                                    </span>
                                </div>
                                <h3 class="email-address">{{ config.email }}</h3>
                            </div>
                            <div class="header-actions">
                                <button @click="openHistoryModal(config)" class="icon-btn-premium" title="Sync History">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                </button>
                                <button @click="openEditEmailModal(config)" class="icon-btn-premium" title="Edit Config">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                    </svg>
                                </button>
                            </div>
                        </div>

                        <!-- User Assignment Section -->
                        <div class="user-assignment-section">
                            <div v-if="config.user_id" class="assigned-user">
                                <div class="user-avatar-ring">
                                    <span class="user-avatar">
                                        {{ familyMembers.find(u => u.id === config.user_id)?.avatar || '👤' }}
                                    </span>
                                </div>
                                <div class="user-details">
                                    <span class="user-name">{{ familyMembers.find(u => u.id === config.user_id)?.full_name || 'Unknown User' }}</span>
                                    <span class="user-label">Inbox Owner</span>
                                </div>
                            </div>
                            <div v-else class="unassigned-state">
                                <div class="unassigned-icon">👥</div>
                                <div class="unassigned-text">
                                    <span class="unassigned-label">Unassigned</span>
                                    <span class="unassigned-hint">Click edit to assign</span>
                                </div>
                            </div>
                            <div class="folder-tag">{{ config.folder }}</div>
                        </div>

                        <!-- Sync Status Timeline -->
                        <div class="sync-timeline">
                            <div v-if="syncStatus && syncStatus.configId === config.id && syncStatus.status === 'running'" class="syncing-state">
                                <div class="sync-spinner"></div>
                                <span class="sync-text">Scanning inbox...</span>
                            </div>
                            <div v-else-if="config.last_sync_at" class="last-sync">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="sync-icon">
                                    <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                </svg>
                                <span>Last synced {{ formatDate(config.last_sync_at).day }}</span>
                            </div>
                            <div v-else class="never-synced">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="warn-icon">
                                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                                    <line x1="12" y1="9" x2="12" y2="13"/>
                                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                                </svg>
                                <span>Never synced</span>
                            </div>
                        </div>

                        <!-- Primary Action -->
                        <button 
                            @click="handleSync(config.id)" 
                            class="sync-btn-premium" 
                            :disabled="syncStatus && syncStatus.status === 'running'"
                            :class="{ 'syncing': syncStatus && syncStatus.configId === config.id && syncStatus.status === 'running' }"
                        >
                            <div class="btn-glow-effect"></div>
                            <span v-if="syncStatus && syncStatus.configId === config.id && syncStatus.status === 'running'">
                                <svg class="btn-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 12a9 9 0 11-6.219-8.56"/>
                                </svg>
                                Syncing...
                            </span>
                            <span v-else>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M13 2L3 14h8l-1 8 10-12h-8l1-8z"/>
                                </svg>
                                Sync Now
                            </span>
                        </button>
                    </div>

                    <!-- Add New Email Card -->
                    <div v-if="emailConfigs.length > 0" class="glass-card add-account-card" @click="showEmailModal = true">
                        <div class="add-icon-circle">+</div>
                        <span>Add Email Account</span>
                    </div>

                    <div v-if="emailConfigs.length === 0" class="empty-email-state">
                        <div class="empty-icon">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                            </svg>
                        </div>
                        <h3>No Email Accounts Linked</h3>
                        <p>Connect your bank email to automatically sync transactions</p>
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

                    <!-- Add New Member Card -->
                    <div class="glass-card add-account-card" @click="openAddMemberModal">
                        <div class="add-icon-circle">+</div>
                        <span>Add Family Member</span>
                    </div>
                </div>
            </div>

            <!-- RULES TAB -->
            <div v-if="activeTab === 'rules'" class="tab-content animate-in">
                <!-- Search Bar -->
                <div class="account-control-bar mb-6">
                    <div class="search-bar-premium no-margin" style="flex: 1; max-width: 300px;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
                            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        <input 
                            type="text" 
                            v-model="searchQuery" 
                            placeholder="Search rules..." 
                            class="search-input"
                        >
                    </div>
                    <div class="header-with-badge" style="margin-left: auto; display: flex; align-items: center; gap: 0.75rem;">
                        <h3 style="margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-main); white-space: nowrap;">Rules</h3>
                        <span class="pulse-status-badge" style="background: #ecfdf5; color: #047857;">{{ filteredRules.length }} Total</span>
                    </div>
                </div>

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

                    <!-- Add New Rule Card -->
                    <div v-if="!searchQuery" class="glass-card add-account-card" @click="openAddModal">
                        <div class="add-icon-circle">+</div>
                        <span>Add New Rule</span>
                    </div>
                </div>
                
                <div v-if="filteredRules.length === 0" class="empty-placeholder">
                    <p>{{ searchQuery ? 'No rules match your search.' : 'No rules found. Define rules to automate categorization.' }}</p>
                </div>
            </div>

            <!-- CATEGORIES TAB -->
            <div v-if="activeTab === 'categories'" class="tab-content animate-in">
                <!-- Search Bar -->
                <div class="account-control-bar mb-6">
                    <div class="search-bar-premium no-margin" style="flex: 1; max-width: 300px;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
                            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        <input 
                            type="text" 
                            v-model="searchQuery" 
                            placeholder="Search categories..." 
                            class="search-input"
                        >
                    </div>
                    <div class="header-with-badge" style="margin-left: auto; display: flex; align-items: center; gap: 0.75rem;">
                        <h3 style="margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-main); white-space: nowrap;">Categories</h3>
                        <span class="pulse-status-badge" style="background: #ecfdf5; color: #047857;">{{ categories.filter(c => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase())).length }} Total</span>
                    </div>
                </div>

                <div class="settings-grid">
                    <div v-for="cat in categories.filter(c => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase()))" :key="cat.id" class="glass-card category-card" :style="{ borderLeft: `4px solid ${cat.color || '#e5e7eb'}` }">
                        <div class="category-card-content">
                            <div class="cat-icon-wrapper" :style="{ background: `${cat.color || '#e5e7eb'}15` }">
                                <span class="cat-icon-large">{{ cat.icon }}</span>
                            </div>
                            <h3 class="cat-name">{{ cat.name }}</h3>
                        </div>
                        <div class="card-actions">
                            <button @click="openEditCategoryModal(cat)" class="btn-icon-circle">✏️</button>
                            <button @click="deleteCategory(cat.id)" class="btn-icon-circle danger">🗑️</button>
                        </div>
                    </div>

                    <!-- Add New Category Card -->
                    <div v-if="!searchQuery" class="glass-card add-account-card" @click="openAddCategoryModal">
                        <div class="add-icon-circle">+</div>
                        <span>Add Category</span>
                    </div>
                </div>

                <div v-if="categories.filter(c => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase())).length === 0 && searchQuery" class="empty-placeholder">
                    <p>No categories match "{{ searchQuery }}"</p>
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

                    <div v-if="newAccount.type === 'CREDIT_CARD'" class="form-row">
                        <div class="form-group half">
                            <label class="form-label">Billing Day (1-31)</label>
                            <input type="number" v-model.number="newAccount.billing_day" class="form-input" min="1" max="31" placeholder="e.g. 15" />
                        </div>
                        <div v-if="newAccount.type === 'CREDIT_CARD'" class="form-group half">
                            <label class="form-label">Due Day (1-31)</label>
                            <input type="number" v-model.number="newAccount.due_day" class="form-input" min="1" max="31" placeholder="e.g. 5" />
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

        <!-- Email Config Modal - PREMIUM REDESIGN -->
        <div v-if="showEmailModal" class="modal-overlay-global" @click.self="showEmailModal = false">
            <div class="email-modal-premium">
                <!-- Modal Header -->
                <div class="email-modal-header">
                    <div class="header-icon-wrapper">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                        </svg>
                    </div>
                    <div class="header-text">
                        <h2 class="email-modal-title">{{ editingEmailConfig ? 'Edit Email Configuration' : 'Connect Email Account' }}</h2>
                        <p class="email-modal-subtitle">{{ editingEmailConfig ? 'Update your email sync settings' : 'Link your bank email for automatic transaction imports' }}</p>
                    </div>
                    <button class="email-modal-close" @click="showEmailModal = false">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
                
                <form @submit.prevent="saveEmailConfig" class="email-modal-form">
                    <!-- Connection Details Section -->
                    <div class="modal-section">
                        <div class="section-header">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 12h-8m8 0a9 9 0 11-18 0 9 9 0 0118 0zM8 12V8l4-4 4 4v4"/>
                            </svg>
                            <h3>Connection Details</h3>
                        </div>
                        
                        <div class="form-grid grid-2">
                            <div class="form-field">
                                <label>Email Address</label>
                                <div class="input-with-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon">
                                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                                        <polyline points="22,6 12,13 2,6"/>
                                    </svg>
                                    <input v-model="emailForm.email" class="premium-input" required placeholder="name@gmail.com" />
                                </div>
                            </div>
                            
                            <div class="form-field">
                                <label>App Password</label>
                                <div class="input-with-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon">
                                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                        <path d="M7 11V7a5 5 0 0110 0v4"/>
                                    </svg>
                                    <input type="password" v-model="emailForm.password" class="premium-input" required placeholder="•••• •••• •••• ••••" />
                                </div>
                            </div>

                            <div class="form-field">
                                <label>IMAP Server</label>
                                <input v-model="emailForm.host" class="premium-input" required placeholder="imap.gmail.com" />
                            </div>
                            
                            <div class="form-field">
                                <label>Folder</label>
                                <input v-model="emailForm.folder" class="premium-input" placeholder="INBOX" />
                            </div>
                        </div>

                        <div class="field-hint">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="16" x2="12" y2="12"/>
                                <line x1="12" y1="8" x2="12.01" y2="8"/>
                            </svg>
                            Use a generated <strong>App Password</strong>, not your main password.
                        </div>
                    </div>

                    <!-- Assignment Section -->
                    <div class="modal-section">
                        <div class="section-header">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                                <circle cx="12" cy="7" r="4"/>
                            </svg>
                            <h3>Ownership & Automation</h3>
                        </div>
                        
                        <div class="form-grid grid-2">
                            <div class="form-field">
                                <label>Assign to Family Member</label>
                                <CustomSelect 
                                    v-model="emailForm.user_id as any" 
                                    :options="[
                                        { label: '👤 Unassigned (Self)', value: null as any },
                                        ...familyMembers.map(m => ({ label: `${m.avatar || '👤'} ${m.full_name || m.email}`, value: (m.id as any) }))
                                    ]"
                                    placeholder="Select inbox owner"
                                />
                            </div>

                            <div class="toggle-field-premium">
                                <div class="toggle-content">
                                    <div class="toggle-icon-wrapper active">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 12a9 9 0 11-6.219-8.56"/>
                                        </svg>
                                    </div>
                                    <div class="toggle-info">
                                        <span class="toggle-title">Auto Sync</span>
                                    </div>
                                </div>
                                <label class="switch-premium">
                                    <input type="checkbox" v-model="emailForm.auto_sync">
                                    <span class="slider-premium"></span>
                                </label>
                            </div>
                        </div>

                        <div class="field-hint">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                            Imported transactions will automatically assign to the owner. Syncs every 15 mins.
                        </div>
                    </div>

                    <!-- Advanced Actions (Edit Mode Only) -->
                    <div v-if="editingEmailConfig" class="advanced-actions-section">
                        <div class="advanced-actions-header">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="1"/>
                                <circle cx="12" cy="5" r="1"/>
                                <circle cx="12" cy="19" r="1"/>
                            </svg>
                            <span>Advanced & History Controls</span>
                        </div>
                        
                        <div class="form-grid grid-2 mb-2">
                            <div class="form-field">
                                <label>Custom Sync Point</label>
                                <input type="datetime-local" v-model="emailForm.last_sync_at" class="premium-input" style="height: 40px;" />
                            </div>
                            <div class="advanced-actions-buttons" style="align-self: flex-end; gap: 0.5rem;">
                                <button type="button" @click="rewindSync(3)" class="btn-advanced" style="height: 40px; flex: 1;" title="Rescan last 3 hours">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="1 4 1 10 7 10"/>
                                        <path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
                                    </svg>
                                    Rewind 3h
                                </button>
                                <button type="button" @click="resetSyncHistory" class="btn-advanced" style="height: 40px; flex: 1;" title="Reset all history tracking">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M21 12a9 9 0 11-6.219-8.56"/>
                                        <path d="M12 7v5l3 3"/>
                                    </svg>
                                    Reset
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Modal Footer -->
                    <div class="email-modal-footer">
                        <button v-if="editingEmailConfig" type="button" @click="deleteEmailConfig(editingEmailConfig)" class="btn-advanced danger mr-auto">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                            Remove Configuration
                        </button>
                        <button type="button" @click="showEmailModal = false" class="btn-secondary-premium">Cancel</button>
                        <button type="submit" class="btn-primary-premium">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                            {{ editingEmailConfig ? 'Update Configuration' : 'Connect Account' }}
                        </button>
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

                    <div class="form-row">
                        <div class="form-group half">
                            <label class="form-label">Date of Birth</label>
                            <input type="date" v-model="memberForm.dob" class="form-input" />
                        </div>
                        <div class="form-group half">
                            <label class="form-label">PAN Number</label>
                            <div style="position: relative;">
                                <input :type="showPan ? 'text' : 'password'" v-model="memberForm.pan_number" class="form-input" style="padding-right: 2.5rem;" placeholder="ABCDE1234F" maxlength="10" />
                                <button type="button" @click="showPan = !showPan" style="position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; opacity: 0.5;">
                                    {{ showPan ? '🙈' : '👁️' }}
                                </button>
                            </div>
                        </div>
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

.header-with-badge {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
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

/* Category Card Styling */
.category-card {
    padding: 1.25rem;
    transition: all 0.2s ease;
}

.category-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.category-card-content {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
}

.cat-icon-wrapper {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.cat-icon-large {
    font-size: 1.5rem;
    line-height: 1;
}

.cat-name {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-main);
    margin: 0;
}

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

/* ==================== PREMIUM EMAIL CARDS ==================== */
.email-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 1.5rem;
}

.email-card-premium {
    position: relative;
    background: white;
    border-radius: 1.25rem;
    padding: 1.5rem;
    border: 1px solid #e5e7eb;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    overflow: hidden;
}

.email-card-premium:hover {
    border-color: #d1d5db;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
}

/* Status Stripe */
.status-stripe {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #10b981, #34d399);
    opacity: 0.8;
}

.status-stripe.inactive {
    background: linear-gradient(90deg, #9ca3af, #d1d5db);
    opacity: 0.5;
}

.status-stripe.auto-sync {
    background: linear-gradient(90deg, #6366f1, #818cf8, #6366f1);
    background-size: 200% 100%;
    animation: gradient-slide 3s ease infinite;
}

@keyframes gradient-slide {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}

/* Card Header */
.email-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.25rem;
}

.email-info {
    flex: 1;
}

.email-status-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    position: relative;
}

.pulse-dot.active {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.pulse-dot.active::after {
    content: '';
    position: absolute;
    top: -4px;
    left: -4px;
    right: -4px;
    bottom: -4px;
    border-radius: 50%;
    border: 2px solid #10b981;
    animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: .7; }
}

@keyframes pulse-ring {
    0% { transform: scale(0.8); opacity: 1; }
    100% { transform: scale(1.4); opacity: 0; }
}

.pulse-dot.inactive {
    background: #9ca3af;
}

.server-label {
    font-size: 0.75rem;
    color: #6b7280;
    font-weight: 500;
}

.auto-sync-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.125rem 0.5rem;
    background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
    color: white;
    font-size: 0.65rem;
    font-weight: 600;
    border-radius: 0.375rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.email-address {
    font-size: 1.125rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}

.header-actions {
    display: flex;
    gap: 0.5rem;
}

.icon-btn-premium {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e5e7eb;
    background: white;
    border-radius: 0.625rem;
    cursor: pointer;
    transition: all 0.2s;
    color: #6b7280;
}

.icon-btn-premium:hover {
    background: #f9fafb;
    border-color: #d1d5db;
    color: #111827;
    transform: translateY(-1px);
}

/* User Assignment Section */
.user-assignment-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
    border-radius: 0.875rem;
    margin-bottom: 1rem;
}

.assigned-user {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex: 1;
}

.user-avatar-ring {
    position: relative;
    width: 44px;
    height: 44px;
    background: linear-gradient(135deg, #6366f1, #818cf8);
    border-radius: 50%;
    padding: 3px;
}

.user-avatar {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    background: white;
    border-radius: 50%;
    font-size: 1.25rem;
}

.user-details {
    display: flex;
    flex-direction: column;
}

.user-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: #111827;
}

.user-label {
    font-size: 0.7rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.unassigned-state {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex: 1;
}

.unassigned-icon {
    width: 40px;
    height: 40px;
    background: #f3f4f6;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    opacity: 0.6;
}

.unassigned-text {
    display: flex;
    flex-direction: column;
}

.unassigned-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: #9ca3af;
}

.unassigned-hint {
    font-size: 0.7rem;
    color: #9ca3af;
}

.folder-tag {
    padding: 0.375rem 0.75rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: #6b7280;
}

/* Sync Timeline */
.sync-timeline {
    padding: 0.75rem 0;
    margin-bottom: 1rem;
    border-top: 1px solid #f3f4f6;
    border-bottom: 1px solid #f3f4f6;
}

.syncing-state, .last-sync, .never-synced {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
}

.sync-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid #e5e7eb;
    border-top-color: #6366f1;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.sync-text {
    color: #6366f1;
    font-weight: 500;
}

.last-sync {
    color: #6b7280;
}

.sync-icon {
    color: #10b981;
}

.never-synced {
    color: #f59e0b;
}

.warn-icon {
    color: #f59e0b;
}

/* Primary Sync Button */
.sync-btn-premium {
    width: 100%;
    position: relative;
    padding: 0.875rem 1.5rem;
    background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
    color: white;
    border: none;
    border-radius: 0.75rem;
    font-weight: 600;
    font-size: 0.9375rem;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.sync-btn-premium:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.4);
}

.sync-btn-premium:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.sync-btn-premium.syncing {
    background: linear-gradient(90deg, #6366f1, #818cf8, #6366f1);
    background-size: 200% 100%;
    animation: gradient-slide 2s ease infinite;
}

.btn-glow-effect {
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.3) 0%, transparent 70%);
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
}

.sync-btn-premium:hover:not(:disabled) .btn-glow-effect {
    opacity: 1;
}

.btn-spinner {
    animation: spin 1s linear infinite;
}

/* Sync Alert Premium */
.sync-alert-premium {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.25rem;
    border-radius: 1rem;
    margin-bottom: 1.5rem;
    border-left: 4px solid;
}

.sync-alert-premium.completed {
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    border-left-color: #10b981;
}

.sync-alert-premium.error {
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    border-left-color: #ef4444;
}

.alert-icon {
    font-size: 1.5rem;
}

.alert-body {
    flex: 1;
}

.alert-body strong {
    display: block;
    font-weight: 600;
    color: #111827;
    margin-bottom: 0.25rem;
}

.alert-body p {
    margin: 0;
    font-size: 0.875rem;
    color: #6b7280;
}

.alert-close {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.05);
    border: none;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: background 0.2s;
    color: #6b7280;
    font-size: 1.125rem;
}

.alert-close:hover {
    background: rgba(0, 0, 0, 0.1);
}

/* Empty State */
.empty-email-state {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
}

.empty-icon {
    margin-bottom: 1.5rem;
    color: #d1d5db;
}

.empty-email-state h3 {
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    margin: 0 0 0.5rem 0;
}

.empty-email-state p {
    font-size: 0.9375rem;
    color: #6b7280;
    margin: 0 0 2rem 0;
    max-width: 400px;
}

.empty-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.875rem 1.75rem;
    background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
    color: white;
    border: none;
    border-radius: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.empty-cta:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.4);
}

/* Email Sync Button */
.sync-btn-premium {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.75rem 1.25rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    border: none;
    border-radius: 0.75rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
}

.sync-btn-premium:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
}

.sync-btn-premium:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.sync-btn-premium span {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.btn-glow-effect {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
}

.btn-spinner {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* ==================== PREMIUM EMAIL MODAL - CLEAN LIGHT THEME ==================== */
.email-modal-premium {
    background: #ffffff;
    border-radius: 1rem;
    max-width: 800px;
    width: 95%;
    max-height: 98vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    border: 1px solid #e2e8f0;
    color: #1e293b;
}

.email-modal-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #f1f5f9;
    background: #ffffff;
}

.header-icon-wrapper {
    width: 36px;
    height: 36px;
    background: #6366f1;
    border-radius: 0.625rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
}

.header-text {
    flex: 1;
}

.email-modal-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    margin: 0;
    letter-spacing: -0.025em;
    position: relative;
    z-index: 1;
}

.email-modal-subtitle {
    font-size: 0.75rem;
    color: #64748b;
    margin: 0;
    position: relative;
    z-index: 1;
}

.email-modal-close {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.03);
    border: 1px solid rgba(0, 0, 0, 0.05);
    border-radius: 0.75rem;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    color: #6b7280;
    flex-shrink: 0;
    position: relative;
    z-index: 1;
}

.email-modal-close:hover {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.2);
    color: #dc2626;
    transform: rotate(90deg);
}

.email-modal-form {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 1.25rem;
    background: #ffffff;
}

.email-modal-form::-webkit-scrollbar {
    width: 6px;
}

.email-modal-form::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 10px;
}

.modal-section {
    margin-bottom: 0.875rem;
}

.modal-section:last-child {
    margin-bottom: 0;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid #f1f5f9;
}

.section-header svg {
    color: #6366f1;
}

.section-header h3 {
    font-size: 0.8125rem;
    font-weight: 700;
    color: #475569;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.form-grid {
    display: grid;
    gap: 0.625rem;
}

.form-grid.grid-2 {
    grid-template-columns: repeat(2, 1fr);
}

.form-field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.form-field label {
    font-size: 0.8125rem;
    font-weight: 600;
    color: #4b5563;
    margin-left: 0.25rem;
}

.input-with-icon {
    position: relative;
}

.input-icon {
    position: absolute;
    left: 1rem;
    top: 50%;
    transform: translateY(-50%);
    color: #9ca3af;
    pointer-events: none;
}

.input-with-icon .premium-input {
    padding-left: 2.75rem;
}

.premium-input {
    width: 100%;
    padding: 0.625rem 0.875rem;
    background: rgba(255, 255, 255, 0.8);
    border: 1.5px solid #e5e7eb;
    border-radius: 0.75rem;
    font-size: 0.875rem;
    color: #111827;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.premium-input:focus {
    outline: none;
    background: white;
    border-color: #6366f1;
    box-shadow: 
        0 0 0 4px rgba(99, 102, 241, 0.1),
        0 4px 12px -2px rgba(0, 0, 0, 0.05);
}

.premium-input::placeholder {
    color: #9ca3af;
}

.field-hint {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: #64748b;
    line-height: 1.4;
    padding: 0.5rem 0.75rem;
    background: #f8fafc;
    border-radius: 0.625rem;
    border: 1px solid #f1f5f9;
    margin-top: 0.125rem;
}

.field-hint svg {
    flex-shrink: 0;
    margin-top: 0.125rem;
    color: #6366f1;
}

.field-hint strong {
    color: #374151;
}

.toggle-field-premium {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.625rem 1rem;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 0.875rem;
    border: 1px solid rgba(0, 0, 0, 0.05);
    margin-top: 0;
    align-self: flex-end;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toggle-field-premium:hover {
    background: rgba(0, 0, 0, 0.04);
    border-color: rgba(0, 0, 0, 0.1);
}

.toggle-content {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.toggle-icon-wrapper {
    width: 32px;
    height: 32px;
    background: white;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e5e7eb;
    color: #6b7280;
    transition: all 0.3s;
}

.toggle-icon-wrapper.active {
    background: rgba(99, 102, 241, 0.05);
    border-color: rgba(99, 102, 241, 0.2);
    color: #6366f1;
}

.toggle-info {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.toggle-title {
    font-size: 0.8125rem;
    font-weight: 700;
    color: #374151;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.toggle-description {
    font-size: 0.75rem;
    color: #6b7280;
}

.switch-premium {
    position: relative;
    display: inline-block;
    width: 48px;
    height: 26px;
}

.switch-premium input {
    opacity: 0;
    width: 0;
    height: 0;
}

.switch-premium .slider-premium {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #e5e7eb;
    transition: .4s cubic-bezier(0.4, 0, 0.2, 1);
    border-radius: 34px;
}

.switch-premium .slider-premium:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: .4s cubic-bezier(0.4, 0, 0.2, 1);
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.switch-premium input:checked + .slider-premium {
    background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.2);
}

.switch-premium input:checked + .slider-premium:before {
    transform: translateX(22px);
    background-color: #ffffff;
}
.advanced-actions-section {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px dashed #e2e8f0;
}

.premium-input.compact {
    padding: 0.625rem 0.875rem;
    font-size: 0.875rem;
}

.mr-auto {
    margin-right: auto;
}

.mb-3 {
    margin-bottom: 0.75rem;
}

.advanced-actions-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    color: #6b7280;
    font-size: 0.8125rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.advanced-actions-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
}

.btn-advanced {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.625rem;
    height: 40px; /* Reduced to standard 40px */
    padding: 0 1rem;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}

.btn-advanced:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
    color: #1e293b;
}

.btn-advanced.danger {
    color: #ef4444;
    border-color: #fee2e2;
    background: #fef2f2;
}

.btn-advanced.danger:hover {
    background: #fee2e2;
    border-color: #fecaca;
}

.email-modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    padding: 0.875rem 1.5rem;
    margin-top: 1rem;
    border-top: 1px solid #f1f5f9;
    background: #f8fafc;
}

.btn-secondary-premium {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 40px; /* Reduced to standard 40px */
    padding: 0 1.25rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-secondary-premium:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
}

.btn-primary-premium {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 40px; /* Reduced to standard 40px */
    padding: 0 1.5rem;
    background: #6366f1;
    color: white;
    border: none;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2);
}

.btn-primary-premium:hover {
    background: #4f46e5;
    transform: translateY(-1px);
    box-shadow: 0 6px 8px -1px rgba(99, 102, 241, 0.3);
}

/* --- Premium Accounts Tab CSS --- */
.account-card-premium {
    position: relative;
    padding: 1.25rem;
    transition: all 0.2s ease;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.4);
    background: linear-gradient(145deg, rgba(255,255,255,0.7), rgba(255,255,255,0.4));
}

.account-card-premium:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.3);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
}

.acc-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
}

.acc-icon-wrapper {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    background: #f3f4f6;
    color: #4b5563;
}
.acc-icon-wrapper.bank { background: #dbeafe; color: #1e40af; }
.acc-icon-wrapper.credit_card { background: #fee2e2; color: #991b1b; }
.acc-icon-wrapper.investment { background: #d1fae5; color: #065f46; }
.acc-icon-wrapper.wallet { background: #ffedd5; color: #9a3412; }

.verified-badge-mini {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    background: #10b981;
    color: white;
    font-size: 0.65rem;
    border-radius: 50%;
    margin-right: 0.5rem;
}

.acc-name {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-main);
    margin-bottom: 0.25rem;
}

.acc-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
}

.acc-mask {
    background: rgba(0,0,0,0.05);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-family: monospace;
}

.acc-card-footer {
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px dashed rgba(0,0,0,0.05);
}

.acc-balance-group {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
}

.acc-balance-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
}

.acc-balance-val {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--color-text-main);
}
.acc-balance-val.text-red { color: #ef4444; }

.balance-tag {
    font-size: 0.7rem;
    color: #ef4444;
    font-weight: 600;
    background: #fee2e2;
    padding: 2px 6px;
    border-radius: 4px;
    vertical-align: middle;
    margin-left: 4px;
}

.acc-limit-group {
    margin-bottom: 0.75rem;
}

.limit-bar-bg {
    width: 100%;
    height: 4px;
    background: #f3f4f6;
    border-radius: 2px;
    margin-bottom: 0.25rem;
    overflow: hidden;
}

.limit-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #818cf8);
    border-radius: 2px;
}

.limit-text {
    font-size: 0.7rem;
    color: var(--color-text-muted);
}

.acc-owner-row {
    display: flex;
    justify-content: flex-end;
}

.owner-pill {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    background: rgba(255,255,255,0.6);
    padding: 0.25rem 0.625rem;
    border-radius: 99px;
    border: 1px solid rgba(0,0,0,0.05);
}

.owner-avatar-xs { font-size: 0.8rem; }
.owner-name-xs { font-size: 0.75rem; font-weight: 600; color: var(--color-text-main); }

.add-account-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 150px;
    background: rgba(255, 255, 255, 0.4);
    border: 2px dashed rgba(99, 102, 241, 0.2); /* Tinted border */
    cursor: pointer;
    transition: all 0.2s;
    color: var(--color-text-muted);
    gap: 0.75rem;
}

.add-account-card:hover {
    background: rgba(255, 255, 255, 0.8);
    border-color: #6366f1;
    color: #6366f1;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
}

.add-icon-circle {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

/* Premium Search Bar */
.search-bar-premium {
    position: relative;
    max-width: 400px;
}

.search-bar-premium .search-icon {
    position: absolute;
    left: 1rem;
    top: 50%;
    transform: translateY(-50%);
    color: #9ca3af;
    pointer-events: none;
}

.search-bar-premium .search-input {
    width: 100%;
    height: 44px;
    padding-left: 2.75rem;
    padding-right: 1rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    font-size: 0.9rem;
    transition: all 0.2s;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.search-bar-premium .search-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    outline: none;
}

.summary-widgets {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}

.mini-stat-card {
    padding: 1rem;
    border-radius: 1rem;
    background: white;
    border: 1px solid rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.stat-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.stat-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.stat-icon-bg {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}
.stat-icon-bg.gray { background: #f3f4f6; }
.stat-icon-bg.green { background: #dcfce7; }
.stat-icon-bg.yellow { background: #fef9c3; }
.stat-icon-bg.red { background: #fee2e2; }

.stat-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--color-text-main);
    letter-spacing: -0.025em;
}

.count-badge {
    background: #e0e7ff;
    color: #4338ca;
    padding: 0.125rem 0.5rem;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 700;
}

.btn-primary-premium:hover {
    background: #4f46e5;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2);
}

/* Animations */
.animate-in {
    animation: modalSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalSlideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

.form-field {
    animation: fadeIn 0.4s ease-out forwards;
    opacity: 0;
}

@keyframes fadeIn {
    to { opacity: 1; }
}

/* Stagger targets */
.form-field:nth-child(1) { animation-delay: 0.1s; }
.form-field:nth-child(2) { animation-delay: 0.15s; }
.form-field:nth-child(3) { animation-delay: 0.2s; }
.form-field:nth-child(4) { animation-delay: 0.25s; }
.modal-section:nth-child(2) .form-field:nth-child(1) { animation-delay: 0.3s; }
.account-control-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}

.search-bar-premium.no-margin {
    margin-bottom: 0 !important;
}

.verified-highlight {
    border-top: 3px solid #10b981;
}

.untrusted-card {
    border-top: 3px solid #f59e0b;
}

.acc-label-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
}

.status-badge-mini {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}
.status-badge-mini.inactive {
    background: #fef3c7;
    color: #b45309;
}

.btn-verify-sm {
    padding: 0.25rem 0.75rem;
    background: #10b981;
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
}
.btn-verify-sm:hover {
    background: #059669;
}

.btn-icon-subtle.danger {
    color: #ef4444;
}
.btn-icon-subtle.danger:hover {
    background: #fee2e2;
}


</style>