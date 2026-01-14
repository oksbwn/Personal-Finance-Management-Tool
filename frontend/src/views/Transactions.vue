<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi, ingestionApi } from '@/api/client'
import { useRoute } from 'vue-router'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import ImportModal from '@/components/ImportModal.vue'

// ... existing code ...

const showImportModal = ref(false)

const route = useRoute()
const notify = useNotificationStore()

const transactions = ref<any[]>([])
const accounts = ref<any[]>([])
const categories = ref<any[]>([])
const triageTransactions = ref<any[]>([])
const loading = ref(true)
const selectedAccount = ref<string>('')
const activeTab = ref<'list' | 'analytics' | 'triage'>('list')
const activeTriageSubTab = ref<'pending' | 'training'>('pending')

// Training State
const unparsedMessages = ref<any[]>([])
const selectedMessage = ref<any | null>(null)
const showLabelForm = ref(false)
const labelForm = ref({
    amount: 0,
    date: new Date().toISOString().slice(0, 16),
    account_mask: '',
    recipient: '',
    ref_id: '',
    generate_pattern: true
})

// Date Filter State
const startDate = ref<string>('')
const endDate = ref<string>('')
const selectedTimeRange = ref<string>('all')

const timeRangeOptions = [
    { label: 'All Time', value: 'all' },
    { label: 'Today', value: 'today' },
    { label: 'This Week', value: 'this-week' },
    { label: 'This Month', value: 'this-month' },
    { label: 'Last Month', value: 'last-month' },
    { label: 'Custom Range', value: 'custom' }
]

// Modal State
const showModal = ref(false)
const isEditing = ref(false)
const editingTxnId = ref<string | null>(null)
const originalCategory = ref<string | null>(null)

// Smart Categorization Modal
const showSmartPrompt = ref(false)
const smartPromptData = ref({
    txnId: '',
    category: '',
    pattern: '',
    count: 0,
    createRule: true,
    applyToSimilar: true
})

// Pagination State
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

// Selection State
const selectedIds = ref<Set<string>>(new Set())
const allSelected = computed(() => {
    return transactions.value.length > 0 && transactions.value.every(t => selectedIds.value.has(t.id))
})

// Form State
const defaultForm = {
    description: '',
    category: '',
    amount: null,
    date: new Date().toISOString().slice(0, 16), // YYYY-MM-DDTHH:mm
    account_id: ''
}
const form = ref({ ...defaultForm })

// Computed for Select Options
const accountOptions = computed(() => {
    return accounts.value.map(a => ({ label: a.name, value: a.id }))
})

const categoryOptions = computed(() => {
     // Transform backend categories to select options
    return categories.value.map(c => ({
        label: `${c.icon || '🏷️'} ${c.name}`,
        value: c.name
    }))
})

async function fetchData() {
    console.log('[Transactions] fetchData called, loading=true')
    loading.value = true
    try {
        if (accounts.value.length === 0) {
           console.log('[Transactions] Fetching accounts and categories...')
           const [accRes, catRes] = await Promise.all([
               financeApi.getAccounts(),
               financeApi.getCategories()
           ])
           accounts.value = accRes.data
           categories.value = catRes.data
           console.log('[Transactions] Loaded', accounts.value.length, 'accounts and', categories.value.length, 'categories')
        }
        if (!selectedAccount.value && route.query.account_id) {
            selectedAccount.value = route.query.account_id as string
        }
        
        let start = startDate.value
        let end = endDate.value

        // Helper to format date for API (YYYY-MM-DD or ISO)
        // If they are coming from the date inputs, they are already YYYY-MM-DD
        
        console.log('[Transactions] Fetching transactions', {
            page: page.value,
            account: selectedAccount.value || 'all',
            start,
            end
        })

        const res = await financeApi.getTransactions(
            selectedAccount.value || undefined, 
            page.value, 
            pageSize.value,
            start || undefined,
            end || undefined
        )
        
        console.log('[Transactions] API response:', res.data)
        transactions.value = res.data.items
        total.value = res.data.total
        
        if (page.value > Math.ceil(total.value / pageSize.value) && page.value > 1) {
            page.value = 1
            fetchData() 
        }
    } catch (e) {
        console.error("[Transactions] Failed to fetch data", e)
        notify.error("Failed to load data")
    } finally {
        loading.value = false
        selectedIds.value.clear()
    }
}

async function fetchTriage() {
    loading.value = true
    try {
        const [res, trainingRes] = await Promise.all([
            financeApi.getTriage(),
            financeApi.getTraining()
        ])
        triageTransactions.value = res.data
        unparsedMessages.value = trainingRes.data
    } catch (e) {
        console.error("Failed to fetch triage", e)
    } finally {
        loading.value = false
    }
}

async function approveTriage(id: string, category?: string) {
    try {
        await financeApi.approveTriage(id, category)
        notify.success("Transaction approved")
        fetchTriage()
        fetchData() // Refresh list in case they switch back
    } catch (e) {
        notify.error("Approval failed")
    }
}

const showDiscardConfirm = ref(false)
const triageIdToDiscard = ref<string | null>(null)

async function rejectTriage(id: string) {
    triageIdToDiscard.value = id
    showDiscardConfirm.value = true
}

async function confirmDiscard() {
    if (!triageIdToDiscard.value) return
    try {
        await financeApi.rejectTriage(triageIdToDiscard.value)
        notify.success("Transaction discarded")
        fetchTriage()
        showDiscardConfirm.value = false
        triageIdToDiscard.value = null
    } catch (e) {
        notify.error("Failed to discard")
    }
}

// --- Interactive Training Methods ---

function startLabeling(msg: any) {
    selectedMessage.value = msg
    // Pre-fill what we can (date extracted from created_at)
    const dateStr = msg.created_at ? new Date(msg.created_at).toISOString().slice(0, 16) : new Date().toISOString().slice(0, 16)
    labelForm.value = {
        amount: 0,
        date: dateStr,
        account_mask: '',
        recipient: '',
        ref_id: '',
        generate_pattern: true
    }
    showLabelForm.value = true
}

async function handleLabelSubmit() {
    if (!selectedMessage.value) return
    try {
        await financeApi.labelMessage(selectedMessage.value.id, labelForm.value)
        notify.success("Message labeled and moved to triage")
        showLabelForm.value = false
        selectedMessage.value = null
        fetchTriage()
    } catch (e) {
        notify.error("Failed to label message")
    }
}

async function dismissTraining(id: string) {
    try {
        await financeApi.dismissTrainingMessage(id)
        notify.success("Message dismissed")
        fetchTriage()
    } catch (e) {
        notify.error("Failed to dismiss message")
    }
}

function handleTimeRangeChange(val: string) {
    const now = new Date()
    const start = new Date()
    const end = new Date()
    
    // Reset to All Time by default
    startDate.value = ''
    endDate.value = ''

    if (val === 'today') {
        start.setHours(0, 0, 0, 0)
        end.setHours(23, 59, 59, 999)
        startDate.value = start.toISOString()
        endDate.value = end.toISOString()
    } else if (val === 'this-week') {
        const day = now.getDay()
        const diff = now.getDate() - day + (day === 0 ? -6 : 1) // adjust when day is sunday
        start.setDate(diff)
        start.setHours(0, 0, 0, 0)
        startDate.value = start.toISOString()
    } else if (val === 'this-month') {
        start.setDate(1)
        start.setHours(0, 0, 0, 0)
        startDate.value = start.toISOString()
    } else if (val === 'last-month') {
        start.setMonth(start.getMonth() - 1)
        start.setDate(1)
        start.setHours(0, 0, 0, 0)
        
        end.setMonth(end.getMonth())
        end.setDate(0) // Last day of previous month
        end.setHours(23, 59, 59, 999)
        
        startDate.value = start.toISOString()
        endDate.value = end.toISOString()
    } else if (val === 'custom') {
        // Keep existing or empty
        return
    }

    page.value = 1
    fetchData()
}

// --- Analytics Computations ---
const analyticsData = computed(() => {
    const data = transactions.value || []
    let income = 0
    let expense = 0
    const catMap: Record<string, number> = {}
    const dateMap: Record<string, number> = {}
    const merchantMap: Record<string, number> = {}
    const accountMap: Record<string, number> = {}
    let weekendSpend = 0
    let weekdaySpend = 0

    // We use all transactions fetched (which is up to pageSize)
    // For proper analytics, we might want to fetch all within range,
    // but for now we analyze the current view's data as requested ("analytics for the grid data")
    data.forEach(t => {
        const amt = Number(t.amount)
        const isExpense = amt < 0
        const absAmt = Math.abs(amt)

        if (!isExpense) income += absAmt
        else {
            expense += absAmt
            // Category Breakdown
            const cat = t.category || 'Uncategorized'
            catMap[cat] = (catMap[cat] || 0) + absAmt

            // Top Merchants
            const merchant = t.recipient || 'Unknown Merchant'
            merchantMap[merchant] = (merchantMap[merchant] || 0) + absAmt

            // Account Distribution
            const accName = getAccountName(t.account_id)
            accountMap[accName] = (accountMap[accName] || 0) + absAmt

            // Weekend vs Weekday
            if (t.date) {
                const day = new Date(t.date).getDay()
                const isWeekend = day === 0 || day === 6 // Sun or Sat
                if (isWeekend) weekendSpend += absAmt
                else weekdaySpend += absAmt
            }
        }

        const dateKey = t.date ? t.date.split('T')[0] : 'Unknown'
        if (isExpense) {
            dateMap[dateKey] = (dateMap[dateKey] || 0) + absAmt
        }
    })

    const sortedCategories = Object.entries(catMap)
        .sort((a, b) => b[1] - a[1])
        .map(([name, value]) => ({ name, value }))

    const sortedMerchants = Object.entries(merchantMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([name, value]) => ({ name, value }))

    const sortedAccounts = Object.entries(accountMap)
        .sort((a, b) => b[1] - a[1])
        .map(([name, value]) => ({ name, value }))

    const sortedTrends = Object.entries(dateMap)
        .sort((a, b) => a[0].localeCompare(b[0]))
        .slice(-14)
        .map(([date, value]) => ({ date, value }))

    return {
        income,
        expense,
        net: income - expense,
        categories: sortedCategories,
        merchants: sortedMerchants,
        accounts: sortedAccounts,
        trends: sortedTrends,
        patterns: {
            weekend: weekendSpend,
            weekday: weekdaySpend,
            weekendPercent: expense > 0 ? (weekendSpend / expense * 100) : 0,
            weekdayPercent: expense > 0 ? (weekdaySpend / expense * 100) : 0
        },
        count: data.length
    }
})

function changePage(newPage: number) {
    if (newPage < 1 || newPage > totalPages.value) return
    page.value = newPage
    fetchData()
}

// Selection Logic
function toggleSelectAll() {
    if (allSelected.value) {
        selectedIds.value.clear()
    } else {
        transactions.value.forEach(t => selectedIds.value.add(t.id))
    }
}

function toggleSelection(id: string) {
    if (selectedIds.value.has(id)) {
        selectedIds.value.delete(id)
    } else {
        selectedIds.value.add(id)
    }
}

const showDeleteConfirm = ref(false)

function deleteSelected() {
    showDeleteConfirm.value = true
}

async function confirmDelete() {
    loading.value = true // fast visual feedback
    try {
        await financeApi.bulkDeleteTransactions(Array.from(selectedIds.value))
        notify.success(`Deleted ${selectedIds.value.size} transactions`)
        fetchData()
        showDeleteConfirm.value = false
        selectedIds.value.clear()
    } catch (e) {
        notify.error("Failed to delete transactions")
        loading.value = false
    }
}

function formatDate(dateStr: string) {
    if (!dateStr) return { day: 'N/A', meta: '' }
    
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) {
        // Try fallback parsing if it's a known non-ISO format
        return { day: '?', meta: dateStr.split('T')[0] || dateStr }
    }
    
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    
    const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    
    // Check if today or yesterday
    if (d.toDateString() === today.toDateString()) {
        return { day: 'Today', meta: time }
    }
    if (d.toDateString() === yesterday.toDateString()) {
        return { day: 'Yesterday', meta: time }
    }
    
    // Regular date - show day number with time
    const monthDay = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    return {
        day: monthDay,
        meta: time
    }
}

function getAccountName(id: string) {
    const acc = accounts.value.find(a => a.id === id)
    return acc ? acc.name : 'Unknown Account'
}


function getCategoryDisplay(name: string) {
    if (!name || name === 'Uncategorized') return { icon: '🏷️', text: 'Uncategorized' }
    const cat = categories.value.find(c => c.name === name)
    if (cat && cat.icon) {
        return { icon: cat.icon, text: cat.name }
    }
    // Fallback for categories without icon
    return { icon: '🏷️', text: name }
}

function getSourceIcon(source: string) {
    if (source === 'CSV' || source === 'EXCEL') return '📁'
    if (source === 'SMS') return '💬'
    return '📝'
}

function openAddModal() {
    isEditing.value = false
    editingTxnId.value = null
    form.value = { 
        ...defaultForm, 
        account_id: selectedAccount.value || (accounts.value[0]?.id || ''),
        date: new Date().toISOString().slice(0, 16)
    }
    showModal.value = true
}

function openEditModal(txn: any) {
    isEditing.value = true
    editingTxnId.value = txn.id
    originalCategory.value = txn.category
    form.value = {
        description: txn.description,
        category: txn.category,
        amount: txn.amount,
        date: txn.date ? txn.date.slice(0, 16) : new Date().toISOString().slice(0, 16),
        account_id: txn.account_id
    }
    showModal.value = true
}

async function handleSubmit() {
    try {
        const payload = {
            description: form.value.description,
            category: form.value.category,
            amount: Number(form.value.amount),
            date: new Date(form.value.date).toISOString(),
            account_id: form.value.account_id
        }

        if (isEditing.value && editingTxnId.value) {
            await financeApi.updateTransaction(editingTxnId.value, payload)
            notify.success("Transaction updated")
            
            // --- Smart Categorization Detection ---
            if (form.value.category !== originalCategory.value && form.value.category) {
                // Find similar transactions to see if we should prompt
                const txn = transactions.value.find(t => t.id === editingTxnId.value)
                if (txn) {
                    const pattern = txn.recipient || txn.description
                    const similarCount = transactions.value.filter(t => 
                        t.id !== txn.id && 
                        (t.category === 'Uncategorized' || !t.category) &&
                        (txn.recipient ? t.recipient === txn.recipient : t.description === txn.description)
                    ).length

                    if (similarCount > 0 || txn.recipient) {
                        smartPromptData.value = {
                            txnId: editingTxnId.value,
                            category: form.value.category,
                            pattern: pattern,
                            count: similarCount,
                            createRule: true,
                            applyToSimilar: similarCount > 0
                        }
                        showSmartPrompt.value = true
                    }
                }
            }
        } else {
            await financeApi.createTransaction(payload)
            notify.success("Transaction added")
        }
        showModal.value = false
        fetchData()
    } catch (e) {
        console.error(e)
        notify.error("Failed to save transaction")
    }
}

async function handleSmartCategorize() {
    try {
        loading.value = true
        const res = await financeApi.smartCategorize({
            transaction_id: smartPromptData.value.txnId,
            category: smartPromptData.value.category,
            create_rule: smartPromptData.value.createRule,
            apply_to_similar: smartPromptData.value.applyToSimilar
        })
        
        if (res.data.success) {
            notify.success(`Success! Updated ${res.data.affected} transactions.`)
            if (res.data.rule_created) {
                notify.success(`Rule saved for "${res.data.pattern}"`)
            }
        }
        showSmartPrompt.value = false
        fetchData()
    } catch (e) {
        notify.error("Smart categorization failed")
    } finally {
        loading.value = false
    }
}

function extractTransactionInfo(description: string) {
    if (!description) return { primary: 'Unknown', secondary: null }
    
    // Common patterns
    const upiPattern = /UPI\/(.*?)\/(.+?)(?:\/|$)/i
    const impsPattern = /IMPS\/(.*?)\/(.+?)(?:\/|$)/i
    const neftPattern = /NEFT\/(.*?)\/(.+?)(?:\/|$)/i
    const atmPattern = /ATM\s+(WDL|CASH)\s*-?\s*(.+?)(?:\s|$)/i
    const posPattern = /POS\s+(.+?)(?:\s|$)/i
    
    // Try UPI
    let match = description.match(upiPattern)
    if (match) {
        return { 
            primary: match[2].trim().substring(0, 25), 
            secondary: 'UPI'
        }
    }
    
    // Try IMPS
    match = description.match(impsPattern)
    if (match) {
        return { 
            primary: match[2].trim().substring(0, 25), 
            secondary: 'IMPS'
        }
    }
    
    // Try NEFT
    match = description.match(neftPattern)
    if (match) {
        return { 
            primary: match[2].trim().substring(0, 25), 
            secondary: 'NEFT'
        }
    }
    
    // Try ATM
    match = description.match(atmPattern)
    if (match) {
        return { 
            primary: match[2].trim().substring(0, 25), 
            secondary: 'ATM'
        }
    }
    
    // Try POS
    match = description.match(posPattern)
    if (match) {
        return { 
            primary: match[1].trim().substring(0, 25), 
            secondary: 'POS'
        }
    }
    
    // Fallback: just truncate
    return { 
        primary: description.substring(0, 30) + (description.length > 30 ? '...' : ''), 
        secondary: null 
    }
}

function switchTab(tab: 'list' | 'analytics' | 'triage') {
    activeTab.value = tab
    if (tab === 'triage') {
        fetchTriage()
    } else {
        fetchData()
    }
}

onMounted(() => {
    fetchData()
    fetchTriage() // Pre-fetch count
})
</script>

<template>
    <MainLayout>
        <!-- Compact Header -->
        <div class="page-header">
            <div class="header-left">
                <h1 class="page-title">Transactions</h1>
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
                        @click="switchTab('analytics')"
                    >
                        Analytics
                    </button>
                    <button 
                        class="tab-btn" 
                        :class="{ active: activeTab === 'triage' }"
                        @click="switchTab('triage')"
                    >
                        Triage <span v-if="triageTransactions.length > 0" class="tab-badge">{{ triageTransactions.length }}</span>
                    </button>
                </div>
                <span class="transaction-count">{{ total }} records</span>
            </div>
            
            <div class="header-actions">
                <CustomSelect 
                    v-model="selectedAccount" 
                    :options="[{ label: 'All Accounts', value: '' }, ...accountOptions]"
                    placeholder="All Accounts"
                    @update:modelValue="page=1; fetchData()"
                    class="account-select"
                />
                
                <button @click="deleteSelected" :disabled="selectedIds.size === 0" class="btn-compact btn-danger">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    </svg>
                    Delete{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
                </button>

                <div class="header-divider"></div>

                <button @click="showImportModal = true" class="btn-compact btn-secondary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                    </svg>
                    Import
                </button>
                
                <button v-if="activeTab !== 'triage'" @click="openAddModal" class="btn-compact btn-primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    Add
                </button>

                <ImportModal :isOpen="showImportModal" @close="showImportModal = false" @import-success="fetchData" />
            </div>
        </div>

        <!-- Filter Bar -->
        <div class="filter-bar" v-if="activeTab !== 'triage'">
            <div class="filter-main">
                <div class="filter-group">
                    <span class="filter-label">Time Range:</span>
                    <div class="range-pill-group">
                        <button 
                            v-for="opt in timeRangeOptions" 
                            :key="opt.value"
                            class="range-pill"
                            :class="{ active: selectedTimeRange === opt.value }"
                            @click="selectedTimeRange = opt.value; handleTimeRangeChange(opt.value)"
                        >
                            {{ opt.label }}
                        </button>
                    </div>
                </div>

                <div class="filter-divider" v-if="selectedTimeRange === 'custom'"></div>

                <div class="filter-group animate-in" v-if="selectedTimeRange === 'custom'">
                    <input type="date" v-model="startDate" class="date-input" @change="page=1; fetchData()" />
                    <span class="filter-separator">to</span>
                    <input type="date" v-model="endDate" class="date-input" @change="page=1; fetchData()" />
                </div>
            </div>

            <button v-if="startDate || endDate" class="btn-link" @click="selectedTimeRange='all'; handleTimeRangeChange('all')">
                Reset
            </button>
        </div>

        <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            Loading transactions...
        </div>

        <div v-else class="content-container animate-in">
            <!-- List View -->
            <div v-if="activeTab === 'list'" class="content-card">
                <table class="modern-table">
                    <thead>
                        <tr>
                            <th class="col-checkbox">
                                <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" :disabled="transactions.length === 0">
                            </th>
                            <th class="col-date">Date</th>
                            <th class="col-recipient">Recipient / Source</th>
                            <th class="col-description">Description</th>
                            <th class="col-amount">Amount</th>
                            <th class="col-actions"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="txn in transactions" :key="txn.id" :class="{ 'row-selected': selectedIds.has(txn.id) }">
                            <td class="col-checkbox">
                                <input type="checkbox" :checked="selectedIds.has(txn.id)" @change="toggleSelection(txn.id)">
                            </td>
                            <td class="col-date">
                                <div class="date-cell">
                                    <div class="date-day">{{ formatDate(txn.date).day }}</div>
                                    <div class="date-meta">{{ formatDate(txn.date).meta }}</div>
                                </div>
                            </td>
                            <td class="col-recipient">
                                <div class="txn-recipient">
                                    <div class="txn-primary">{{ txn.recipient || txn.description }}</div>
                                </div>
                            </td>
                            <td class="col-description">
                                <div class="txn-description">
                                    <div class="txn-description-text">{{ txn.description }}</div>
                                    <div class="txn-meta-row">
                                        <span class="account-badge">{{ getAccountName(txn.account_id) }}</span>
                                        <span class="txn-secondary" v-if="txn.source">{{ txn.source }}</span>
                                        <span v-if="txn.is_ai_parsed" class="ai-badge-mini" title="Extracted using Gemini AI">✨ AI</span>
                                        <span class="category-pill">
                                            <span class="category-icon">{{ getCategoryDisplay(txn.category).icon }}</span>
                                            {{ getCategoryDisplay(txn.category).text }}
                                        </span>
                                        <span class="ref-id-pill" v-if="txn.external_id">
                                            <span class="ref-icon">🆔</span> {{ txn.external_id }}
                                        </span>
                                    </div>
                                </div>
                            </td>
                            <td class="col-amount">
                                <div class="amount-cell" :class="{'is-income': Number(txn.amount) > 0, 'is-expense': Number(txn.amount) < 0}">
                                    <span class="amount-icon">{{ Number(txn.amount) > 0 ? '↑' : '↓' }}</span>
                                    <span class="amount-value">{{ Math.abs(Number(txn.amount)).toFixed(2) }}</span>
                                </div>
                            </td>
                            <td class="col-actions">
                                <button class="icon-btn" @click="openEditModal(txn)" title="Edit">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    </tbody>
                </table>
                
                <div v-if="transactions.length === 0" class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M3 9h18M9 21V9"/>
                    </svg>
                    <p>No transactions found</p>
                </div>
                
                <!-- Compact Pagination -->
                <div class="pagination-bar" v-if="total > 0">
                    <span class="page-info">
                        {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, total) }} of {{ total }}
                    </span>
                    <div class="pagination-controls">
                        <button class="page-btn" :disabled="page === 1" @click="changePage(page - 1)">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M15 18l-6-6 6-6"/>
                            </svg>
                        </button>
                        <button class="page-btn" :disabled="page >= totalPages" @click="changePage(page + 1)">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 18l6-6-6-6"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Analytics View -->
            <div v-if="activeTab === 'analytics'" class="analytics-dashboard">
                <!-- Summary Cards -->
                <div class="summary-grid">
                    <div class="summary-card income">
                        <div class="card-icon">⚡</div>
                        <div class="card-content">
                            <span class="card-label">Total Income</span>
                            <span class="card-value">₹{{ analyticsData.income.toFixed(2) }}</span>
                        </div>
                    </div>
                    <div class="summary-card expense">
                        <div class="card-icon">🔥</div>
                        <div class="card-content">
                            <span class="card-label">Total Expenses</span>
                            <span class="card-value">₹{{ analyticsData.expense.toFixed(2) }}</span>
                        </div>
                    </div>
                    <div class="summary-card net" :class="{ 'is-negative': analyticsData.net < 0 }">
                        <div class="card-icon">{{ analyticsData.net >= 0 ? '💰' : '📉' }}</div>
                        <div class="card-content">
                            <span class="card-label">Net Savings</span>
                            <span class="card-value">₹{{ analyticsData.net.toFixed(2) }}</span>
                        </div>
                    </div>
                </div>

                <div class="analytics-main-grid">
                    <!-- Category Breakdown -->
                    <div class="analytics-card">
                        <h3 class="card-title">Category Breakdown</h3>
                        <div class="category-list">
                            <div v-for="cat in analyticsData.categories" :key="cat.name" class="category-item">
                                <div class="category-info">
                                    <span class="cat-name">{{ cat.name }}</span>
                                    <span class="cat-value">₹{{ cat.value.toFixed(2) }}</span>
                                </div>
                                <div class="progress-bar-bg">
                                    <div 
                                        class="progress-bar-fill" 
                                        :style="{ width: `${(cat.value / analyticsData.expense * 100) || 0}%` }"
                                    ></div>
                                </div>
                            </div>
                            <div v-if="analyticsData.categories.length === 0" class="empty-small">
                                No spending data available
                            </div>
                        </div>
                    </div>

                    <!-- Daily Trend -->
                    <div class="analytics-card">
                        <h3 class="card-title">Daily Spending Trend</h3>
                        <div class="trend-chart-container">
                            <div class="trend-bars">
                                <div 
                                    v-for="day in analyticsData.trends" 
                                    :key="day.date" 
                                    class="trend-bar-wrapper"
                                    :title="`${day.date}: ₹${day.value.toFixed(2)}`"
                                >
                                    <div 
                                        class="trend-bar" 
                                        :style="{ height: `${(day.value / Math.max(...analyticsData.trends.map(d => d.value), 1) * 100)}%` }"
                                    ></div>
                                    <span class="trend-date">{{ day.date.slice(8) }}</span>
                                </div>
                            </div>
                            <div v-if="analyticsData.trends.length === 0" class="empty-small">
                                Not enough data for trend
                            </div>
                        </div>
                    </div>

                    <!-- Top Merchants -->
                    <div class="analytics-card">
                        <h3 class="card-title">Top Merchants</h3>
                        <div class="merchant-list">
                            <div v-for="m in analyticsData.merchants" :key="m.name" class="merchant-item">
                                <span class="m-name">{{ m.name }}</span>
                                <span class="m-value">₹{{ m.value.toFixed(2) }}</span>
                            </div>
                            <div v-if="analyticsData.merchants.length === 0" class="empty-small">
                                No merchant data
                            </div>
                        </div>
                    </div>

                    <!-- Spending Insights -->
                    <div class="analytics-card">
                        <h3 class="card-title">Spending Insights</h3>
                        <div class="insights-content">
                            <div class="insight-section">
                                <h4 class="insight-subtitle">Account Distribution</h4>
                                <div class="account-list">
                                    <div v-for="acc in analyticsData.accounts" :key="acc.name" class="account-item">
                                        <div class="acc-info">
                                            <span>{{ acc.name }}</span>
                                            <span>₹{{ acc.value.toFixed(2) }}</span>
                                        </div>
                                        <div class="mini-bar-bg">
                                            <div class="mini-bar-fill" :style="{ width: `${(acc.value / analyticsData.expense * 100) || 0}%` }"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="insight-divider"></div>

                            <div class="insight-section">
                                <h4 class="insight-subtitle">Weekend vs Weekday</h4>
                                <div class="pattern-bars">
                                    <div class="pattern-item">
                                        <div class="pattern-label">
                                            <span>Weekdays</span>
                                            <span>{{ analyticsData.patterns.weekdayPercent.toFixed(0) }}%</span>
                                        </div>
                                        <div class="pattern-bar-bg">
                                            <div class="pattern-bar-fill weekday" :style="{ width: `${analyticsData.patterns.weekdayPercent}%` }"></div>
                                        </div>
                                    </div>
                                    <div class="pattern-item">
                                        <div class="pattern-label">
                                            <span>Weekends</span>
                                            <span>{{ analyticsData.patterns.weekendPercent.toFixed(0) }}%</span>
                                        </div>
                                        <div class="pattern-bar-bg">
                                            <div class="pattern-bar-fill weekend" :style="{ width: `${analyticsData.patterns.weekendPercent}%` }"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Triage View -->
            <div v-if="activeTab === 'triage'" class="triage-view animate-in">
                <div class="triage-tabs mb-6">
                    <button 
                        class="triage-tab-btn" 
                        :class="{ active: activeTriageSubTab === 'pending' }"
                        @click="activeTriageSubTab = 'pending'"
                    >
                        Pending Inbox ({{ triageTransactions.length }})
                    </button>
                    <button 
                        class="triage-tab-btn" 
                        :class="{ active: activeTriageSubTab === 'training' }"
                        @click="activeTriageSubTab = 'training'"
                    >
                        Training Area ({{ unparsedMessages.length }})
                    </button>
                </div>

                <div v-if="activeTriageSubTab === 'pending'">
                    <div class="alert-info-glass mb-4">
                        <div class="alert-icon">🔒</div>
                        <div class="alert-text">
                            <strong>Review Intake</strong>: These transactions were auto-detected but require categorization or confirmation before affecting your balance.
                        </div>
                    </div>

                    <div class="triage-grid">
                    <div v-for="txn in triageTransactions" :key="txn.id" class="glass-card triage-card">
                        <div class="triage-card-header">
                            <span class="source-tag" :class="txn.source.toLowerCase()">{{ txn.source }}</span>
                            <span v-if="txn.is_ai_parsed" class="ai-badge-mini" title="Extracted using Gemini AI">✨ AI</span>
                            <span class="triage-date">{{ formatDate(txn.date).day }} {{ formatDate(txn.date).meta }}</span>
                        </div>
                        
                        <div class="triage-card-body">
                            <div class="triage-amount-col" :class="txn.amount < 0 ? 'expense' : 'income'">
                                <div class="amount-val">₹{{ Math.abs(txn.amount).toFixed(2) }}</div>
                                <div class="amount-type">{{ txn.amount < 0 ? 'Debit' : 'Credit' }}</div>
                            </div>
                            <div class="triage-details-col">
                                <h3 class="triage-title">{{ txn.recipient || txn.description }}</h3>
                                <div class="triage-meta">
                                    <span class="meta-item">📍 {{ getAccountName(txn.account_id) }}</span>
                                    <span class="meta-item" v-if="txn.description">📝 {{ txn.description }}</span>
                                    <span class="ref-id-pill small" v-if="txn.external_id">🆔 {{ txn.external_id }}</span>
                                </div>
                                <div v-if="txn.raw_message" class="raw-message-preview" :title="txn.raw_message">
                                    Raw: {{ txn.raw_message.substring(0, 60) }}...
                                </div>
                            </div>
                        </div>

                        <div class="triage-card-footer">
                            <button @click="rejectTriage(txn.id)" class="btn-discard">Discard</button>
                            <div class="approval-form">
                                <CustomSelect 
                                    v-model="txn.category" 
                                    :options="categoryOptions"
                                    placeholder="Set Category"
                                    class="triage-select"
                                />
                                <button @click="approveTriage(txn.id, txn.category)" class="btn-approve">Approve</button>
                            </div>
                        </div>
                    </div>
                </div>

                    <div v-if="triageTransactions.length === 0" class="empty-state-triage">
                        <div class="empty-glow-icon">✨</div>
                        <h3>Inbox zero!</h3>
                        <p>No new transactions waiting for review.</p>
                    </div>
                </div>

                <!-- Training Area -->
                <div v-if="activeTriageSubTab === 'training'">
                    <div class="alert-info-glass mb-4 training-alert">
                        <div class="alert-icon">🤖</div>
                        <div class="alert-text">
                            <strong>Interactive Training</strong>: These messages look like transactions but could not be parsed. Label them to help the system learn!
                        </div>
                    </div>

                    <div class="triage-grid">
                        <div v-for="msg in unparsedMessages" :key="msg.id" class="glass-card triage-card training-card">
                            <div class="triage-card-header">
                                <span class="source-tag" :class="msg.source.toLowerCase()">{{ msg.source }}</span>
                                <span class="triage-date">{{ formatDate(msg.created_at).day }}</span>
                            </div>
                            
                            <div class="triage-card-body">
                                <div class="training-content">
                                    <div class="training-sender" v-if="msg.sender">From: {{ msg.sender }}</div>
                                    <div class="training-subject" v-if="msg.subject">Sub: {{ msg.subject }}</div>
                                    <pre class="training-raw-preview">{{ msg.raw_content }}</pre>
                                </div>
                            </div>

                            <div class="triage-card-footer">
                                <button @click="dismissTraining(msg.id)" class="btn-discard">Dismiss</button>
                                <button @click="startLabeling(msg)" class="btn-approve btn-label">Label Fields</button>
                            </div>
                        </div>
                    </div>

                    <div v-if="unparsedMessages.length === 0" class="empty-state-triage">
                        <div class="empty-glow-icon">🛡️</div>
                        <h3>All clear!</h3>
                        <p>No unparsed messages waiting for training.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Global Styled Modal -->
        <div v-if="showModal" class="modal-overlay-global">
            <div class="modal-global">
                <div class="modal-header">
                    <h2 class="modal-title">{{ isEditing ? 'Edit Transaction' : 'Add Transaction' }}</h2>
                    <button class="btn-icon" @click="showModal = false">✕</button>
                </div>

                <form @submit.prevent="handleSubmit">
                    
                    <div class="form-group" v-if="!isEditing">
                        <label class="form-label">Account</label>
                        <CustomSelect 
                            v-model="form.account_id" 
                            :options="accountOptions"
                            placeholder="Select Account"
                        />
                    </div>

                    <div class="form-layout-row">
                        <div class="form-group half">
                            <label class="form-label">Amount (+ Income, - Expense)</label>
                            <input type="number" step="0.01" v-model="form.amount" class="form-input" required placeholder="-50.00" />
                        </div>
                        <div class="form-group half">
                            <label class="form-label">Date</label>
                             <input type="datetime-local" v-model="form.date" class="form-input" required />
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Description</label>
                        <input v-model="form.description" class="form-input" required placeholder="e.g. Grocery shopping" />
                    </div>

                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <CustomSelect 
                            v-model="form.category" 
                            :options="categoryOptions"
                            placeholder="Select Category"
                            allow-new
                        />
                    </div>
                   
                    <div class="modal-footer">
                        <button type="button" @click="showModal = false" class="btn btn-outline">
                            <span class="icon-spacer">✕</span> Cancel
                        </button>
                        <button type="submit" class="btn btn-primary">
                            <span class="icon-spacer">💾</span> Save
                        </button>
                    </div>
                </form>
            </div>
        </div>


        <!-- Smart Categorization Prompt -->
        <div v-if="showSmartPrompt" class="modal-overlay-global">
            <div class="modal-global" style="max-width: 450px;">
                <div class="modal-header">
                    <h2 class="modal-title">Smart Categorization 🧠</h2>
                    <button class="btn-icon" @click="showSmartPrompt = false">✕</button>
                </div>
                <div style="padding: 1.5rem;">
                    <p style="margin-bottom: 1.25rem; color: #4b5563; line-height: 1.5;">
                        You categorized <strong>{{ smartPromptData.pattern }}</strong> as <strong>{{ smartPromptData.category }}</strong>.
                    </p>
                    
                    <div class="smart-options">
                        <label class="smart-option-item" v-if="smartPromptData.count > 0">
                            <input type="checkbox" v-model="smartPromptData.applyToSimilar" class="checkbox-input">
                            <span>Apply to <strong>{{ smartPromptData.count }}</strong> similar uncategorized transactions</span>
                        </label>
                        
                        <label class="smart-option-item">
                            <input type="checkbox" v-model="smartPromptData.createRule" class="checkbox-input">
                            <span>Always categorize <strong>{{ smartPromptData.pattern }}</strong> as <strong>{{ smartPromptData.category }}</strong> in future</span>
                        </label>
                    </div>

                    <div class="modal-footer" style="padding: 1.5rem 0 0 0; border: none; background: transparent;">
                        <button class="btn btn-outline" @click="showSmartPrompt = false">Skip</button>
                        <button class="btn btn-primary" @click="handleSmartCategorize">Confirm</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Delete Confirmation Modal -->
        <div v-if="showDeleteConfirm" class="modal-overlay-global">
            <div class="modal-global" style="max-width: 400px;">
                <div class="modal-header">
                    <h2 class="modal-title">Delete Transactions</h2>
                    <button class="btn-icon" @click="showDeleteConfirm = false">✕</button>
                </div>
                <div style="padding: 1.5rem; text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🗑️</div>
                    <p style="color: #4b5563; margin-bottom: 1.5rem;">
                        Are you sure you want to delete <strong>{{ selectedIds.size }}</strong> selected transactions? This action cannot be undone.
                    </p>
                    <div class="modal-footer" style="padding: 0; border: none; background: transparent; justify-content: center; gap: 1rem;">
                        <button class="btn btn-outline" @click="showDeleteConfirm = false">Cancel</button>
                        <button class="btn btn-danger" @click="confirmDelete" style="background: #ef4444; color: white; border: none;">Delete</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Triage Discard Confirmation Modal -->
        <div v-if="showDiscardConfirm" class="modal-overlay-global">
            <div class="modal-global" style="max-width: 400px;">
                <div class="modal-header">
                    <h2 class="modal-title">Discard Transaction</h2>
                    <button class="btn-icon" @click="showDiscardConfirm = false">✕</button>
                </div>
                <div style="padding: 1.5rem; text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">♻️</div>
                    <p style="color: #4b5563; margin-bottom: 1.5rem;">
                        Discard this potential transaction? It will be removed from your review list.
                    </p>
                    <div class="modal-footer" style="padding: 0; border: none; background: transparent; justify-content: center; gap: 1rem;">
                        <button class="btn btn-outline" @click="showDiscardConfirm = false">Keep It</button>
                        <button class="btn btn-danger" @click="confirmDiscard" style="background: #ef4444; color: white; border: none;">Discard</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Interactive Labeling Modal -->
        <div v-if="showLabelForm" class="modal-overlay-global">
            <div class="modal-global" style="max-width: 800px;">
                <div class="modal-header">
                    <h2 class="modal-title">Label Transaction 🏷️</h2>
                    <button class="btn-icon" @click="showLabelForm = false">✕</button>
                </div>
                
                <div class="labeling-layout">
                    <!-- Left: Raw Message -->
                    <div class="labeling-raw">
                        <h4 class="section-label">Raw Message</h4>
                        <div class="raw-content-box">{{ selectedMessage?.raw_content }}</div>
                        <div class="raw-meta" v-if="selectedMessage?.subject">
                            <strong>Subject:</strong> {{ selectedMessage.subject }}
                        </div>
                    </div>

                    <!-- Right: Form -->
                    <form @submit.prevent="handleLabelSubmit" class="labeling-form">
                        <div class="form-grid-2">
                            <div class="form-group">
                                <label class="form-label">Amount (₹)</label>
                                <input type="number" v-model="labelForm.amount" class="form-input" required step="0.01">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Date</label>
                                <input type="datetime-local" v-model="labelForm.date" class="form-input" required>
                            </div>
                        </div>

                        <div class="form-group">
                            <label class="form-label">Account Mask (Last 4 digits)</label>
                            <input type="text" v-model="labelForm.account_mask" class="form-input" placeholder="e.g. 1234" required maxlength="4">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Recipient / Merchant</label>
                            <input type="text" v-model="labelForm.recipient" class="form-input" placeholder="e.g. Starbucks">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Reference ID (Optional)</label>
                            <input type="text" v-model="labelForm.ref_id" class="form-input" placeholder="UTR / TXN ID">
                        </div>

                        <div class="form-group check-group">
                            <input type="checkbox" id="genPattern" v-model="labelForm.generate_pattern">
                            <label for="genPattern">Learn this pattern for future messages</label>
                        </div>

                        <div class="modal-footer" style="padding: 1.5rem 0 0 0; background: transparent;">
                            <button type="button" class="btn btn-outline" @click="showLabelForm = false">Cancel</button>
                            <button type="submit" class="btn btn-primary">Create Pending Transaction</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
/* Triage Sub-Tabs */
.triage-tabs {
    display: flex;
    gap: 1rem;
    border-bottom: 2px solid #f3f4f6;
    padding-bottom: 0.1rem;
}

.triage-tab-btn {
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: #6b7280;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: -2px;
}

.triage-tab-btn:hover {
    color: #4f46e5;
}

.triage-tab-btn.active {
    color: #4f46e5;
    border-bottom-color: #4f46e5;
}

/* Training Logic Styles */
.training-card {
    border-left: 4px solid #f59e0b;
}

.training-content {
    background: #fdfaf5;
    padding: 0.75rem;
    border-radius: 0.5rem;
    border: 1px dashed #fbbf24;
}

.training-sender, .training-subject {
    font-size: 0.75rem;
    font-weight: 600;
    color: #92400e;
    margin-bottom: 0.25rem;
}

.training-raw-preview {
    font-family: 'Monaco', 'Consolas', monospace;
    font-size: 0.75rem;
    line-height: 1.4;
    color: #4b5563;
    white-space: pre-wrap;
    margin: 0;
}

.btn-label {
    background: #f59e0b;
    border-color: #f59e0b;
}

.btn-label:hover {
    background: #d97706;
}

/* Labeling Modal Layout */
.labeling-layout {
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 2rem;
    padding: 1.5rem;
}

.labeling-raw {
    background: #f9fafb;
    border-radius: 0.75rem;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
}

.raw-content-box {
    background: white;
    padding: 1rem;
    border-radius: 0.5rem;
    font-family: monospace;
    font-size: 0.8125rem;
    white-space: pre-wrap;
    border: 1px solid #f3f4f6;
    flex-grow: 1;
    overflow-y: auto;
    max-height: 400px;
    color: #111827;
}

.raw-meta {
    margin-top: 1rem;
    font-size: 0.75rem;
    color: #6b7280;
}

.section-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 0.75rem;
    letter-spacing: 0.05em;
}

.labeling-form .form-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.check-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #eef2ff;
    padding: 0.75rem;
    border-radius: 0.5rem;
    margin-top: 1rem;
}

.check-group input {
    width: 1.125rem;
    height: 1.125rem;
    cursor: pointer;
}

.check-group label {
    font-size: 0.8125rem;
    color: #4338ca;
    font-weight: 500;
    cursor: pointer;
}

/* Legacy styles below ... */
/* Modern Compact Design System */

/* Page Header */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
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

.header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.account-select {
    min-width: 200px;
}

.account-select :deep(.select-trigger) {
    padding: 0.5rem 0.875rem;
    font-size: 0.875rem;
    display: flex;
    align-items: center;
}

/* Compact Buttons - match dropdown */
.btn-compact {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 0.375rem;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
}

.btn-compact svg {
    flex-shrink: 0;
}

.btn-compact:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-primary {
    background: #4f46e5;
    color: white;
    border-color: #4f46e5;
}

.btn-primary:hover:not(:disabled) {
    background: #4338ca;
    border-color: #4338ca;
}

.btn-secondary {
    background: white;
    color: #374151;
    border-color: #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
    background: #f9fafb;
    border-color: #9ca3af;
}

.btn-danger {
    background: white;
    color: #dc2626;
    border-color: #fecaca;
}

.btn-danger:hover:not(:disabled) {
    background: #fef2f2;
    border-color: #fca5a5;
}

/* Loading State */
.loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 4rem 2rem;
    color: #6b7280;
    font-size: 0.875rem;
}

.spinner {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid #e5e7eb;
    border-top-color: #4f46e5;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Content Card */
.table-container {
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    overflow-x: auto;
    border: 1px solid #e5e7eb;
    margin-bottom: 1.5rem;
    position: relative;
}

/* Modern Table */
.modern-table {
    width: 100%;
    min-width: 900px;
    border-collapse: collapse;
    font-size: 0.875rem;
    table-layout: fixed;
}

.modern-table thead th {
    background: #f9fafb;
    padding: 0.5rem 0.6rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.7rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid #e5e7eb;
    position: sticky;
    top: 0;
    z-index: 10;
}

.modern-table tbody td {
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid #f3f4f6;
    color: #374151;
    vertical-align: middle;
}

.modern-table tbody tr:last-child td {
    border-bottom: none;
}

/* Zebra striping */
.modern-table tbody tr:nth-child(even) {
    background: #fafafa;
}

.modern-table tbody tr:hover {
    background: #f3f4f6;
}

.modern-table tbody tr.row-selected {
    background: #eff6ff;
}

.modern-table tbody tr.row-selected:hover {
    background: #dbeafe;
}

/* Column Sizing */
.col-checkbox { 
    width: 40px; 
    text-align: center;
    padding-left: 1rem !important;
}
.col-icon { 
    width: 36px; 
    text-align: center;
    padding-left: 0.5rem !important;
    padding-right: 0.5rem !important;
}
.col-date { 
    width: 110px;
    min-width: 110px;
    font-variant-numeric: tabular-nums;
}
.col-recipient {
    width: 250px;
    min-width: 200px;
    font-weight: 500;
}
.col-description { 
    width: auto;
    min-width: 300px;
    color: #4b5563;
}
.col-amount { 
    width: 120px;
    text-align: right;
    padding-right: 1.5rem !important;
}
.col-actions { 
    width: 50px; 
    text-align: center;
    padding-right: 1rem !important;
}

/* Table Elements */
.source-icon {
    font-size: 1.125rem;
    opacity: 0.7;
}

/* Date Cell */
.date-cell {
    line-height: 1.3;
}

.date-day {
    font-size: 0.875rem;
    font-weight: 600;
    color: #111827;
}

.date-meta {
    font-size: 0.65rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

/* Transaction Description */
.txn-description {
    line-height: 1.4;
}

.txn-primary {
    color: #111827;
    font-weight: 600;
    font-size: 0.875rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 0rem;
}

.txn-description-text {
    font-size: 0.75rem;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 0.125rem;
}

.txn-meta-row {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex-wrap: wrap;
}

.account-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    background: #eff6ff;
    color: #1e40af;
    border-radius: 9999px;
    font-size: 0.65rem;
    font-weight: 500;
    white-space: nowrap;
}

.txn-secondary {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    background: #fef3c7;
    color: #92400e;
    border-radius: 9999px;
    font-size: 0.65rem;
    text-transform: uppercase;
    font-weight: 500;
    letter-spacing: 0.025em;
    white-space: nowrap;
}

/* Category Pill */
.category-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.125rem 0.5rem;
    background: #f3f4f6;
    color: #4b5563;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 500;
    white-space: nowrap;
}

.category-icon {
    font-size: 0.875rem;
}

/* Amount Cell with Icon */
.amount-cell {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.375rem;
}

.amount-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.125rem;
    height: 1.125rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 700;
}

.amount-cell.is-income .amount-icon {
    background: #d1fae5;
    color: #059669;
}

.amount-cell.is-expense .amount-icon {
    background: #fee2e2;
    color: #dc2626;
}

.amount-value {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    font-size: 0.875rem;
}

.amount-cell.is-income .amount-value {
    color: #059669;
}

.amount-cell.is-expense .amount-value {
    color: #374151;
}

/* Remove old amount styling */
.amount-positive {
    color: #059669;
    font-weight: 600;
}

.amount-negative {
    color: #374151;
    font-weight: 500;
}

/* Filter Bar */
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
    font-size: 0.7rem;
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
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.filter-divider {
    width: 1px;
    height: 1.5rem;
    background: #e5e7eb;
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

.animate-in {
    animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.header-divider {
    width: 1px;
    height: 1.5rem;
    background: #e5e7eb;
    margin: 0 0.5rem;
}

.btn-link {
    background: none;
    border: none;
    color: #4f46e5;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 0.375rem;
    transition: background 0.2s;
}

.btn-link:hover {
    background: #eff6ff;
}

/* Icon Button */
.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 0.375rem;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.15s ease;
}

.icon-btn:hover {
    background: #f3f4f6;
    color: #111827;
}

/* Empty State */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 2rem;
    color: #9ca3af;
    gap: 0.75rem;
}

.empty-state svg {
    opacity: 0.5;
}

.empty-state p {
    margin: 0;
    font-size: 0.875rem;
}

/* Pagination Bar */
.pagination-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-top: 1px solid #e5e7eb;
    background: #fafafa;
}

.page-info {
    font-size: 0.875rem;
    color: #6b7280;
}

.pagination-controls {
    display: flex;
    gap: 0.25rem;
}

.page-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    padding: 0;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    color: #374151;
    cursor: pointer;
    transition: all 0.15s ease;
}

.page-btn:hover:not(:disabled) {
    background: #f9fafb;
    border-color: #d1d5db;
}

.page-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* Modal Button Overrides for Existing Modals */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 0.875rem;
    border-radius: 0.375rem;
    font-weight: 500;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s ease;
    border: 1px solid transparent;
}

.btn-outline {
    background: white;
    color: #374151;
    border-color: #d1d5db;
}

.btn-outline:hover {
    background: #f9fafb;
    border-color: #9ca3af;
}

/* Form Styles */
.form-layout-row { 
    display: flex; 
    gap: 1.5rem; 
}

.half { 
    flex: 1; 
}

.form-input {
    width: 100%; 
    padding: 0.625rem 0.875rem;
    border: 1px solid #d1d5db; 
    border-radius: 0.375rem;
    font-size: 0.875rem; 
    transition: all 0.15s;
    background: white;
}

.form-input:focus {
    border-color: #4f46e5; 
    outline: none;
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.icon-spacer { 
    margin-right: 0.5rem; 
}

/* Smart Options */
.smart-options {
    background: #f9fafb;
    border-radius: 0.5rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    border: 1px solid #e5e7eb;
}

.smart-option-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    cursor: pointer;
    font-size: 0.875rem;
    color: #374151;
}

.checkbox-input {
    margin-top: 0.125rem;
    width: 1rem;
    height: 1rem;
    cursor: pointer;
}
/* Tabs Styling */
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

.tab-btn:hover:not(.active) {
    color: #111827;
}

.tab-btn.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

/* Analytics Dashboard */
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.summary-card {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    padding: 1.5rem;
    background: white;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    transition: transform 0.2s;
}

.summary-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
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

.income .card-icon { background: #ecfdf5; }
.expense .card-icon { background: #fef2f2; }
.net .card-icon { background: #eff6ff; }
.net.is-negative .card-icon { background: #fff7ed; }

.card-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}

.card-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
}

.income .card-value { color: #059669; }
.expense .card-value { color: #dc2626; }
.net.is-negative .card-value { color: #d97706; }

.analytics-main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
}

.analytics-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 1.5rem;
}

/* Category List */
.category-list {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}

.category-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
}

.cat-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: #374151;
}

.cat-value {
    font-size: 0.875rem;
    font-weight: 700;
    color: #111827;
}

.progress-bar-bg {
    height: 0.5rem;
    background: #f3f4f6;
    border-radius: 9999px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #4f46e5, #818cf8);
    border-radius: 9999px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Trend Chart */
.trend-chart-container {
    height: 200px;
    display: flex;
    align-items: flex-end;
    padding-top: 1rem;
}

.trend-bars {
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
    width: 100%;
    height: 100%;
}

.trend-bar-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    height: 100%;
    justify-content: flex-end;
}

.trend-bar {
    width: 100%;
    background: #e0e7ff;
    border-radius: 0.25rem 0.25rem 0 0;
    min-height: 2px;
    transition: all 0.3s;
    cursor: help;
}

.trend-bar:hover {
    background: #4f46e5;
}

.trend-date {
    font-size: 0.65rem;
    color: #9ca3af;
    font-weight: 500;
}

.empty-small {
    padding: 3rem;
    text-align: center;
    color: #9ca3af;
    font-size: 0.875rem;
}

@media (max-width: 1024px) {
    .analytics-main-grid {
        grid-template-columns: 1fr;
    }
}
/* Merchant List */
.merchant-list {
    display: flex;
    flex-direction: column;
    gap: 0.875rem;
}

.merchant-item {
    display: flex;
    justify-content: space-between;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f3f4f6;
}

.merchant-item:last-child {
    border-bottom: none;
}

.m-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
}

.m-value {
    font-size: 0.875rem;
    font-weight: 700;
    color: #111827;
}

/* Spending Insights */
.insights-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.insight-subtitle {
    font-size: 0.75rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}

.account-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.account-item {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.acc-info {
    display: flex;
    justify-content: space-between;
    font-size: 0.8125rem;
    font-weight: 500;
    color: #4b5563;
}

.mini-bar-bg {
    height: 4px;
    background: #f3f4f6;
    border-radius: 2px;
}

.mini-bar-fill {
    height: 100%;
    background: #4f46e5;
    border-radius: 2px;
}

.insight-divider {
    height: 1px;
    background: #e5e7eb;
}

.pattern-bars {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}

.pattern-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.8125rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.pattern-bar-bg {
    height: 8px;
    background: #f3f4f6;
    border-radius: 4px;
    overflow: hidden;
}

.pattern-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.8s ease;
}

.pattern-bar-fill.weekday { background: #4f46e5; }
.pattern-bar-fill.weekend { background: #f59e0b; }

/* Triage Area Styles */
.tab-badge {
    background: #ef4444;
    color: white;
    font-size: 0.7rem;
    padding: 0.1rem 0.4rem;
    border-radius: 999px;
    margin-left: 0.3rem;
    font-weight: 700;
}

.triage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 1.5rem;
}

.triage-card {
    display: flex;
    flex-direction: column;
    padding: 1.25rem;
    border: 1px solid rgba(255,255,255,0.2);
    transition: transform 0.2s, box-shadow 0.2s;
}

.triage-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.1);
}

.triage-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.source-tag {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    background: #e5e7eb;
    color: #4b5563;
}

.source-tag.sms { background: #dcfce7; color: #166534; }
.source-tag.email { background: #dbeafe; color: #1e40af; }

.triage-date {
    font-size: 0.75rem;
    color: #9ca3af;
}

.triage-card-body {
    display: flex;
    gap: 1.25rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid rgba(0,0,0,0.05);
}

.triage-amount-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 100px;
    padding: 0.75rem;
    background: rgba(0,0,0,0.03);
    border-radius: 12px;
}

.triage-amount-col.expense .amount-val { color: #ef4444; }
.triage-amount-col.income .amount-val { color: #10b981; }

.amount-val {
    font-size: 1.125rem;
    font-weight: 700;
}

.amount-type {
    font-size: 0.7rem;
    text-transform: uppercase;
    font-weight: 600;
    opacity: 0.6;
}

.triage-details-col {
    flex: 1;
    min-width: 0; /* Critical for flex child truncation */
    display: flex;
    flex-direction: column;
}

.triage-title {
    font-size: 1rem;
    font-weight: 600;
    color: #111827;
    margin: 0 0 0.5rem 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.triage-meta {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
}

.meta-item {
    font-size: 0.8125rem;
    color: #6b7280;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.raw-message-preview {
    font-family: monospace;
    font-size: 0.7rem;
    padding: 0.5rem;
    background: #f9fafb;
    border-radius: 6px;
    color: #9ca3af;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.triage-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 1rem;
    gap: 1rem;
}

.approval-form {
    display: flex;
    gap: 0.5rem;
    flex: 1;
}

.triage-select {
    flex: 1;
}

.btn-approve {
    background: #4f46e5;
    color: white;
    border: none;
    padding: 0 1rem;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

.btn-approve:hover { background: #4338ca; }

.btn-discard {
    background: transparent;
    color: #9ca3af;
    border: 1px solid #e5e7eb;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-discard:hover {
    color: #ef4444;
    border-color: #fecaca;
    background: #fef2f2;
}

.empty-state-triage {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 5rem 2rem;
    text-align: center;
}

.empty-glow-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    text-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
}

.alert-info-glass {
    display: flex;
    gap: 0.75rem;
    padding: 1rem;
    background: rgba(59, 130, 246, 0.05);
    border: 1px solid rgba(59, 130, 246, 0.1);
    border-radius: 12px;
    align-items: center;
}

.alert-icon { font-size: 1.25rem; }
.alert-text { font-size: 0.875rem; color: #1e40af; }
.ref-id-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: rgba(var(--brand-primary-rgb, 99, 102, 241), 0.1);
    border: 1px solid rgba(var(--brand-primary-rgb, 99, 102, 241), 0.2);
    border-radius: 100px;
    font-size: 10px;
    font-family: inherit;
    color: var(--text-secondary);
    letter-spacing: 0.02em;
    font-weight: 500;
}

.ref-id-pill.small {
    padding: 1px 6px;
    font-size: 9px;
}

.ref-icon {
    font-size: 10px;
    filter: grayscale(1) opacity(0.7);
}
.ai-badge-mini {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    background: #eef2ff;
    color: #4f46e5;
    padding: 0px 6px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    border: 1px solid rgba(79, 70, 229, 0.2);
    cursor: help;
}
</style>
