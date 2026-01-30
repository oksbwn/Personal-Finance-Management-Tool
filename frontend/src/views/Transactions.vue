<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import { useRoute } from 'vue-router'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import ImportModal from '@/components/ImportModal.vue'
import { useCurrency } from '@/composables/useCurrency'

// ... existing code ...

import SpendingHeatmap from '@/components/SpendingHeatmap.vue'

const showImportModal = ref(false)
const { formatAmount } = useCurrency()

const route = useRoute()
const notify = useNotificationStore()

const transactions = ref<any[]>([])
const accounts = ref<any[]>([])
const categories = ref<any[]>([])
const expenseGroups = ref<any[]>([])
const triageTransactions = ref<any[]>([])
const budgets = ref<any[]>([])
const loans = ref<any[]>([])
const loading = ref(true)
const selectedAccount = ref<string>('')
const activeTab = ref<'list' | 'analytics' | 'triage' | 'heatmap'>('list')
const activeTriageSubTab = ref<'pending' | 'training'>('pending')

const heatmapData = ref<any[]>([])
const loadingHeatmap = ref(false)

async function fetchHeatmapData() {
    loadingHeatmap.value = true
    try {
        const res = await financeApi.getHeatmapData(
            startDate.value || undefined,
            endDate.value || undefined,
            undefined // user_id
        )
        heatmapData.value = res.data
    } catch (e) {
        console.error("Failed to fetch heatmap data", e)
        notify.error("Failed to load heatmap")
    } finally {
        loadingHeatmap.value = false
    }
}

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
    category: 'Uncategorized',
    type: 'DEBIT',
    exclude_from_reports: false,
    generate_pattern: true
})

// Triage & Training Pagination/Selection
const triagePagination = ref({ total: 0, limit: 10, skip: 0 })
const triageSearchQuery = ref('')
const triageSourceFilter = ref<'ALL' | 'SMS' | 'EMAIL'>('ALL')

// Main List Filters
const searchQuery = ref('')
const categoryFilter = ref('')

const trainingPagination = ref({ total: 0, limit: 10, skip: 0 })
const filteredTriageTransactions = computed(() => {
    let items = triageTransactions.value

    if (triageSourceFilter.value !== 'ALL') {
        items = items.filter(t => t.source === triageSourceFilter.value)
    }

    if (triageSearchQuery.value) {
        const q = triageSearchQuery.value.toLowerCase()
        items = items.filter(t =>
            (t.description?.toLowerCase().includes(q)) ||
            (t.recipient?.toLowerCase().includes(q)) ||
            (t.external_id?.toLowerCase().includes(q))
        )
    }

    return items
})

const selectedTriageIds = ref<string[]>([])
const selectedTrainingIds = ref<string[]>([])
const isProcessingBulk = ref(false)

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
const originalExclude = ref(false)
const potentialMatches = ref<any[]>([])
const isSearchingMatches = ref(false)
const matchesSearched = ref(false)

// Smart Categorization Modal
const showSmartPrompt = ref(false)
const smartPromptData = ref({
    txnId: '',
    category: '',
    pattern: '',
    count: 0,
    createRule: true,
    applyToSimilar: true,
    excludeFromReports: false
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
    account_id: '',
    is_transfer: false,
    to_account_id: '',
    linked_transaction_id: '',
    exclude_from_reports: false,
    is_emi: false,
    loan_id: '',
    expense_group_id: ''
}
const form = ref({ ...defaultForm })

// Computed for Select Options
const accountOptions = computed(() => {
    return accounts.value.map(a => ({ label: a.name, value: a.id }))
})

const loanOptions = computed(() => {
    return loans.value.map(l => ({ label: l.name, value: l.id }))
})

const expenseGroupOptions = computed(() => {
    return expenseGroups.value.map(g => ({ label: g.name, value: g.id }))
})

const categoryOptions = computed(() => {
    const list: any[] = []

    // Helper to flatten recursive categories
    const flatten = (cats: any[], depth = 0) => {
        cats.forEach(c => {
            const prefix = depth > 0 ? '　'.repeat(depth) + '└ ' : ''
            list.push({
                label: `${prefix}${c.icon || '🏷️'} ${c.name}`,
                value: c.name
            })
            if (c.subcategories && c.subcategories.length > 0) {
                flatten(c.subcategories, depth + 1)
            }
        })
    }

    flatten(categories.value)

    // Ensure Uncategorized is an option if not present
    if (!list.find(o => o.value === 'Uncategorized')) {
        list.push({ label: '🏷️ Uncategorized', value: 'Uncategorized' })
    }

    return list
})

const currentCategoryBudget = computed(() => {
    if (!form.value.category || form.value.is_transfer) return null
    return budgets.value.find(b => b.category === form.value.category) || null
})

async function fetchData() {
    console.log('[Transactions] fetchData called, loading=true')
    loading.value = true
    try {
        if (accounts.value.length === 0) {
            const [accRes, catRes, budgetRes, loanRes, groupRes] = await Promise.all([
                financeApi.getAccounts(),
                financeApi.getCategories(true),
                financeApi.getBudgets(),
                financeApi.getLoans(),
                financeApi.getExpenseGroups()
            ])
            accounts.value = accRes.data
            categories.value = catRes.data
            budgets.value = budgetRes.data
            loans.value = loanRes.data
            expenseGroups.value = groupRes.data
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
            end || undefined,
            searchQuery.value || undefined,
            categoryFilter.value || undefined
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

async function fetchTriage(resetSkip = false) {
    loading.value = true
    try {
        if (resetSkip) {
            triagePagination.value.skip = 0
            trainingPagination.value.skip = 0
        }

        // Ensure we have accounts and categories for rendering triage items
        if (accounts.value.length === 0 || categories.value.length === 0) {
            const [accRes, catRes] = await Promise.all([
                financeApi.getAccounts(),
                financeApi.getCategories(true)
            ])
            accounts.value = accRes.data
            categories.value = catRes.data
        }

        const [res, trainingRes] = await Promise.all([
            financeApi.getTriage({ limit: triagePagination.value.limit, skip: triagePagination.value.skip }),
            financeApi.getTraining({ limit: trainingPagination.value.limit, skip: trainingPagination.value.skip })
        ])

        triageTransactions.value = res.data.items.map((t: any) => ({
            ...t,
            category: t.category || 'Uncategorized',
            is_transfer: !!t.is_transfer,
            create_rule: false
        }))
        triagePagination.value.total = res.data.total
        selectedTriageIds.value = []

        unparsedMessages.value = trainingRes.data.items
        trainingPagination.value.total = trainingRes.data.total
        selectedTrainingIds.value = []

    } catch (e) {
        console.error("Failed to fetch triage", e)
    } finally {
        loading.value = false
    }
}

async function handleBulkRejectTriage() {
    if (selectedTriageIds.value.length === 0) return
    isProcessingBulk.value = true
    try {
        await financeApi.bulkRejectTriage(selectedTriageIds.value, createIgnoreRule.value)
        if (createIgnoreRule.value) {
            notify.success(`Ignored ${selectedTriageIds.value.length} patterns for the future`)
        } else {
            notify.success(`Discarded ${selectedTriageIds.value.length} items`)
        }
        createIgnoreRule.value = false
        fetchTriage()
    } catch (e) {
        notify.error("Bulk reject failed")
    } finally {
        isProcessingBulk.value = false
    }
}

async function handleBulkDismissTraining() {
    if (selectedTrainingIds.value.length === 0) return
    // For simplicity, we can reuse the same modal if we clear the single ID
    trainingIdToDiscard.value = null
    showTrainingDiscardConfirm.value = true
}

async function handleConfirmGlobalTrainingDismiss() {
    if (trainingIdToDiscard.value) {
        await confirmTrainingDiscard()
    } else {
        await handleBulkDismissTrainingConfirm()
        showTrainingDiscardConfirm.value = false
    }
}
// The finally block for handleBulkDismissTraining was misplaced in the instruction snippet.
// It should be part of the handleBulkDismissTraining function itself.
// The original handleBulkDismissTraining already had a finally block.
// I will ensure the finally block is correctly associated with handleBulkDismissTraining.
// The instruction snippet implies a change to handleBulkDismissTraining, but the finally block
// was already there. I'll keep the existing finally block for handleBulkDismissTraining.


function toggleSelectAllTriage() {
    if (selectedTriageIds.value.length === triageTransactions.value.length) {
        selectedTriageIds.value = []
    } else {
        selectedTriageIds.value = triageTransactions.value.map(t => t.id)
    }
}

function toggleSelectAllTraining() {
    if (selectedTrainingIds.value.length === unparsedMessages.value.length) {
        selectedTrainingIds.value = []
    } else {
        selectedTrainingIds.value = unparsedMessages.value.map(m => m.id)
    }
}

async function approveTriage(txn: any) {
    try {
        const res = await financeApi.approveTriage(txn.id, {
            category: txn.category,
            is_transfer: txn.is_transfer,
            to_account_id: txn.to_account_id,
            exclude_from_reports: txn.exclude_from_reports,
            create_rule: false // Rule creation now handled by prompt
        })
        notify.success("Transaction approved")

        // --- Smart Categorization Prompt Logic ---
        if (!txn.is_transfer && txn.category && txn.category !== 'Uncategorized') {
            const pattern = txn.recipient || txn.description
            // Use the ACTUAL newly created transaction ID from the backend response
            const newTxnId = res.data.transaction_id

            smartPromptData.value = {
                txnId: newTxnId,
                category: txn.category,
                pattern: pattern,
                count: 0,
                createRule: true,
                applyToSimilar: false,
                excludeFromReports: false
            }
            showSmartPrompt.value = true
        }

        fetchTriage()
        fetchData() // Refresh list in case they switch back
    } catch (e) {
        notify.error("Approval failed")
    }
}

const showDiscardConfirm = ref(false)
const showTrainingDiscardConfirm = ref(false) // Added
const createIgnoreRule = ref(false)
const triageIdToDiscard = ref<string | null>(null)
const trainingIdToDiscard = ref<string | null>(null) // Added

async function rejectTriage(id: string) {
    triageIdToDiscard.value = id
    showDiscardConfirm.value = true
}

async function confirmDiscard() {
    if (!triageIdToDiscard.value) return
    try {
        await financeApi.rejectTriage(triageIdToDiscard.value, createIgnoreRule.value)
        if (createIgnoreRule.value) {
            notify.success("Pattern will be ignored in future")
        } else {
            notify.success("Transaction discarded")
        }
        fetchTriage()
        showDiscardConfirm.value = false
        triageIdToDiscard.value = null
        createIgnoreRule.value = false
    } catch (e) {
        notify.error("Failed to discard")
    }
}

// --- Interactive Training Methods ---

function startLabeling(msg: any) {
    selectedMessage.value = msg
    const content = msg.raw_content || ''

    // 1. Smart Extraction Heuristics
    // Amount: Look for numbers after currency keywords
    const amtMatch = content.match(/(?:Rs\.?|INR|₹|Amt)\s*([\d,]+(?:\.\d{1,2})?)/i)
    let suggestedAmt = 0
    if (amtMatch) {
        suggestedAmt = parseFloat(amtMatch[1].replace(/,/g, ''))
    }

    // Account Mask: Look for 3-4 digits after account keywords
    const accMatch = content.match(/(?:A\/c|Acct|ending|XX|card)\s*(\d{3,4})/i)
    const suggestedMask = accMatch ? accMatch[1] : ''

    // Ref ID: Look for long alphanumeric strings
    const refMatch = content.match(/(?:Ref|UTR|TXN|ID)\s*:?\s*([A-Z0-9]{8,})/i)
    const suggestedRef = refMatch ? refMatch[1] : ''

    // Type: Detect Credit keywords
    const isCredit = /credit|received|deposit|incoming|refund/i.test(content)
    const suggestedType = isCredit ? 'CREDIT' : 'DEBIT'

    // 2. Pre-fill the form
    const dateStr = msg.created_at ? new Date(msg.created_at).toISOString().slice(0, 16) : new Date().toISOString().slice(0, 16)

    labelForm.value = {
        amount: suggestedAmt,
        date: dateStr,
        account_mask: suggestedMask,
        recipient: '', // Still hard to guess reliably
        ref_id: suggestedRef,
        category: 'Uncategorized',
        type: suggestedType,
        exclude_from_reports: false,
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
    trainingIdToDiscard.value = id
    showTrainingDiscardConfirm.value = true
}

async function confirmTrainingDiscard() {
    if (!trainingIdToDiscard.value) return
    try {
        await financeApi.dismissTrainingMessage(trainingIdToDiscard.value, createIgnoreRule.value)
        if (createIgnoreRule.value) {
            notify.success("Pattern will be ignored in future")
        } else {
            notify.success("Message dismissed")
        }
        fetchTriage()
        showTrainingDiscardConfirm.value = false
        trainingIdToDiscard.value = null
        createIgnoreRule.value = false
    } catch (e) {
        notify.error("Failed to dismiss")
    }
}

async function handleBulkDismissTrainingConfirm() {
    if (selectedTrainingIds.value.length === 0) return
    try {
        await financeApi.bulkDismissTraining(selectedTrainingIds.value, createIgnoreRule.value)
        if (createIgnoreRule.value) {
            notify.success(`Ignored ${selectedTrainingIds.value.length} patterns for future`)
        } else {
            notify.success("Messages dismissed")
        }
        fetchTriage()
        createIgnoreRule.value = false
        selectedTrainingIds.value = [] // Clear selection after bulk dismiss
    } catch (e) {
        notify.error("Bulk dismiss failed")
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
    if (!name || name === 'Uncategorized') return { icon: '🏷️', text: 'Uncategorized', color: '#9ca3af' }

    // Find category in the flat list
    const cat = categories.value.find(c => c.name === name)
    if (cat) {
        let text = cat.name
        // If it has a parent, show a bit of hierarchy in the list
        if (cat.parent_name) {
            text = `${cat.parent_name} › ${cat.name}`
        }
        return { icon: cat.icon || '🏷️', text: text, color: cat.color || '#3B82F6' }
    }

    // Fallback for categories without matched object
    return { icon: '🏷️', text: name, color: '#9ca3af' }
}

function getExpenseGroupName(id: string) {
    if (!id) return null
    const group = expenseGroups.value.find(g => g.id === id)
    return group ? group.name : null
}


function openAddModal() {
    isEditing.value = false
    editingTxnId.value = null
    form.value = {
        ...defaultForm,
        account_id: selectedAccount.value || (accounts.value[0]?.id || ''),
        date: new Date().toISOString().slice(0, 16),
        is_transfer: false,
        to_account_id: '',
        linked_transaction_id: '',
        is_emi: false,
        loan_id: '',
        expense_group_id: ''
    }
    potentialMatches.value = []
    matchesSearched.value = false
    showModal.value = true
}

// Watch for transfer toggle to auto-set category
watch(() => form.value.is_transfer, (isTransfer) => {
    if (isTransfer) {
        form.value.category = 'Transfer'
        form.value.exclude_from_reports = true
    } else if (form.value.category === 'Transfer') {
        form.value.category = '' // Reset if it was transfer
        form.value.exclude_from_reports = false
    }
})

function openEditModal(txn: any) {
    isEditing.value = true
    editingTxnId.value = txn.id
    originalCategory.value = txn.category
    originalExclude.value = txn.exclude_from_reports || false
    form.value = {
        description: txn.description,
        category: txn.category,
        amount: txn.amount,
        date: txn.date ? txn.date.slice(0, 16) : new Date().toISOString().slice(0, 16),
        account_id: txn.account_id,
        is_transfer: txn.is_transfer || false,
        to_account_id: txn.transfer_account_id || '',
        linked_transaction_id: txn.linked_transaction_id || '',
        exclude_from_reports: txn.exclude_from_reports || false,
        is_emi: txn.is_emi || false,
        loan_id: txn.loan_id || '',
        expense_group_id: txn.expense_group_id || ''
    }
    potentialMatches.value = []
    matchesSearched.value = false
    showModal.value = true
}

async function handleSubmit() {
    try {
        const payload = {
            description: form.value.description,
            category: form.value.category,
            amount: Number(form.value.amount),
            date: new Date(form.value.date).toISOString(),
            account_id: form.value.account_id,
            is_transfer: form.value.is_transfer,
            to_account_id: form.value.to_account_id,
            linked_transaction_id: form.value.linked_transaction_id,
            exclude_from_reports: form.value.exclude_from_reports,
            is_emi: form.value.is_emi,
            loan_id: form.value.loan_id,
            expense_group_id: form.value.expense_group_id
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
                            applyToSimilar: similarCount > 0,
                            excludeFromReports: false
                        }
                        showSmartPrompt.value = true
                    }
                }
            }

            if (form.value.exclude_from_reports && !originalExclude.value) {
                const txn = transactions.value.find(t => t.id === editingTxnId.value)
                if (txn) {
                    const pattern = txn.recipient || txn.description
                    smartPromptData.value = {
                        txnId: editingTxnId.value,
                        category: form.value.category || 'Uncategorized',
                        pattern: pattern,
                        count: 0,
                        createRule: true,
                        applyToSimilar: true,
                        excludeFromReports: true
                    }
                    showSmartPrompt.value = true
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
            apply_to_similar: smartPromptData.value.applyToSimilar,
            exclude_from_reports: smartPromptData.value.excludeFromReports
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


function switchTab(tab: 'list' | 'analytics' | 'triage' | 'heatmap') {
    activeTab.value = tab
    if (tab === 'triage') {
        fetchTriage()
    } else if (tab === 'heatmap') {
        fetchHeatmapData()
    } else {
        fetchData()
    }
}

// Search debounce
let searchDebounce: any = null
watch(searchQuery, () => {
    if (searchDebounce) clearTimeout(searchDebounce)
    searchDebounce = setTimeout(() => {
        page.value = 1
        fetchData()
    }, 400)
})

// Match Finding Logic
async function findMatches() {
    if (!form.value.to_account_id || !form.value.amount || !form.value.date) return

    isSearchingMatches.value = true
    matchesSearched.value = false
    try {
        const txnDate = new Date(form.value.date)
        const startDate = new Date(txnDate)
        startDate.setDate(startDate.getDate() - 3)
        const endDate = new Date(txnDate)
        endDate.setDate(endDate.getDate() + 3)

        const res = await financeApi.getTransactions(
            form.value.to_account_id,
            1,
            50, // limit
            startDate.toISOString().slice(0, 10),
            endDate.toISOString().slice(0, 10)
        )

        // Filter for opposite amount (with tolerance)
        // If current txn is -100 (sending), look for +100 (receiving)
        // If current txn is +100 (receiving), look for -100 (sending)
        const targetAmount = -Number(form.value.amount)

        potentialMatches.value = res.data.items.filter((t: any) => {
            // Basic tolerance check for float issues or fees
            return Math.abs(t.amount - targetAmount) < 1.0 &&
                // Don't link to self if something weird happens
                t.id !== editingTxnId.value &&
                // Don't link if already matched to someone else
                (!t.linked_transaction_id || t.linked_transaction_id === editingTxnId.value)
        })

        matchesSearched.value = true
    } catch (e) {
        console.error("Match search failed", e)
    } finally {
        isSearchingMatches.value = false
    }
}

function selectMatch(match: any) {
    if (form.value.linked_transaction_id === match.id) {
        form.value.linked_transaction_id = '' // Deselect
    } else {
        form.value.linked_transaction_id = match.id
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
                    <button class="tab-btn" :class="{ active: activeTab === 'list' }" @click="activeTab = 'list'">
                        List
                    </button>
                    <button class="tab-btn" :class="{ active: activeTab === 'triage' }" @click="switchTab('triage')">
                        Triage <span v-if="triageTransactions.length > 0" class="tab-badge">{{ triageTransactions.length
                            }}</span>
                    </button>
                    <button class="tab-btn" :class="{ active: activeTab === 'heatmap' }" @click="switchTab('heatmap')">
                        Heatmap 🗺️
                    </button>
                </div>
                <span class="transaction-count">{{ total }} records</span>
            </div>

            <div class="header-actions">
                <CustomSelect v-model="selectedAccount"
                    :options="[{ label: 'All Accounts', value: '' }, ...accountOptions]" placeholder="All Accounts"
                    @update:modelValue="page = 1; fetchData()" class="account-select" />

                <button @click="deleteSelected" :disabled="selectedIds.size === 0" class="btn-compact btn-danger">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                    Delete{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
                </button>

                <div class="header-divider"></div>

                <button @click="showImportModal = true" class="btn-compact btn-secondary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                    </svg>
                    Import
                </button>

                <button v-if="activeTab !== 'triage'" @click="openAddModal" class="btn-compact btn-primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14" />
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
                        <button v-for="opt in timeRangeOptions" :key="opt.value" class="range-pill"
                            :class="{ active: selectedTimeRange === opt.value }"
                            @click="selectedTimeRange = opt.value; handleTimeRangeChange(opt.value)">
                            {{ opt.label }}
                        </button>
                    </div>
                </div>

                <div class="filter-divider" v-if="selectedTimeRange === 'custom'"></div>

                <div class="filter-group animate-in" v-if="selectedTimeRange === 'custom'">
                    <input type="date" v-model="startDate" class="date-input" @change="page = 1; fetchData()" />
                    <span class="filter-separator">to</span>
                    <input type="date" v-model="endDate" class="date-input" @change="page = 1; fetchData()" />
                </div>

                <div class="filter-divider"></div>

                <div class="filter-group list-search-group">
                    <div class="list-search-container">
                        <span class="search-icon-small">🔍</span>
                        <input type="text" v-model="searchQuery" placeholder="Search description..."
                            class="list-search-input">
                    </div>
                </div>

                <div class="filter-divider"></div>

                <div class="filter-group">
                    <CustomSelect v-model="categoryFilter"
                        :options="[{ label: 'All Categories', value: '' }, ...categoryOptions]"
                        placeholder="All Categories" @update:modelValue="page = 1; fetchData()"
                        class="category-filter-select" />
                </div>
            </div>

            <button v-if="startDate || endDate || searchQuery || categoryFilter" class="btn-link"
                @click="selectedTimeRange = 'all'; startDate = ''; endDate = ''; searchQuery = ''; categoryFilter = ''; fetchData()">
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
                                <input type="checkbox" :checked="allSelected" @change="toggleSelectAll"
                                    :disabled="transactions.length === 0">
                            </th>
                            <th class="col-date">Date</th>
                            <th class="col-recipient">Recipient / Source</th>
                            <th class="col-description">Description</th>
                            <th class="col-amount">Amount</th>
                            <th class="col-actions"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="txn in transactions" :key="txn.id"
                            :class="{ 'row-selected': selectedIds.has(txn.id) }">
                            <td class="col-checkbox">
                                <input type="checkbox" :checked="selectedIds.has(txn.id)"
                                    @change="toggleSelection(txn.id)">
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
                                        <span v-if="txn.is_ai_parsed" class="ai-badge-mini"
                                            title="Extracted using Gemini AI">✨ AI</span>
                                        <span v-if="txn.is_transfer" class="ai-badge-mini"
                                            style="background: #ecfdf5; color: #059669; border-color: #059669;"
                                            title="Auto-detected as internal transfer">🔄 Self-Transfer</span>
                                        <span v-if="txn.exclude_from_reports" class="ai-badge-mini"
                                            style="background: #fee2e2; color: #991b1b; border-color: #fca5a5;"
                                            title="Excluded from reports and analytics">🚫 Excluded</span>
                                        <span v-if="txn.is_emi" class="ai-badge-mini"
                                            style="background: #e0f2fe; color: #0369a1; border-color: #7dd3fc;"
                                            title="Linked to EMI Loan">🏦 EMI Payment</span>
                                        <span class="category-pill"
                                            :style="{ borderLeft: '3px solid ' + getCategoryDisplay(txn.category).color }">
                                            <span class="category-icon">{{ getCategoryDisplay(txn.category).icon
                                                }}</span>
                                            {{ getCategoryDisplay(txn.category).text }}
                                        </span>
                                        <span class="ref-id-pill" v-if="txn.is_transfer">
                                            <span class="ref-icon">🔄</span> Transfer
                                        </span>
                                        <span class="ref-id-pill" v-if="txn.expense_group_id">
                                            <span class="ref-icon">📁</span> {{
                                                getExpenseGroupName(txn.expense_group_id) }}
                                        </span>
                                        <span class="ref-id-pill" v-if="txn.external_id">
                                            <span class="ref-icon">🆔</span> {{ txn.external_id }}
                                        </span>
                                    </div>
                                </div>
                            </td>
                            <td class="col-amount">
                                <div class="amount-cell"
                                    :class="{ 'is-income': Number(txn.amount) > 0 && !txn.is_transfer, 'is-expense': Number(txn.amount) < 0 && !txn.is_transfer, 'is-transfer': txn.is_transfer }">
                                    <span class="amount-icon">{{ txn.is_transfer ? '🔄' : (Number(txn.amount) > 0 ? '↓'
                                        : '↑') }}</span>
                                    <span class="amount-value">{{ formatAmount(Math.abs(Number(txn.amount))) }}</span>
                                </div>
                            </td>
                            <td class="col-actions">
                                <button class="icon-btn" @click="openEditModal(txn)" title="Edit">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                        stroke-width="2">
                                        <path
                                            d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    </tbody>
                </table>

                <div v-if="transactions.length === 0" class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M3 9h18M9 21V9" />
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
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2">
                                <path d="M15 18l-6-6 6-6" />
                            </svg>
                        </button>
                        <button class="page-btn" :disabled="page >= totalPages" @click="changePage(page + 1)">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2">
                                <path d="M9 18l6-6-6-6" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>



            <!-- Triage View -->
            <div v-if="activeTab === 'triage'" class="triage-view animate-in">
                <div class="triage-tabs mb-6">
                    <button class="triage-tab-btn" :class="{ active: activeTriageSubTab === 'pending' }"
                        @click="activeTriageSubTab = 'pending'">
                        Pending Inbox ({{ triagePagination.total }})
                    </button>
                    <button class="triage-tab-btn" :class="{ active: activeTriageSubTab === 'training' }"
                        @click="activeTriageSubTab = 'training'">
                        Training Area ({{ trainingPagination.total }})
                    </button>
                </div>

                <div v-if="activeTriageSubTab === 'pending'">
                    <div class="alert-info-glass mb-4">
                        <div class="alert-icon">🔒</div>
                        <div class="alert-text">
                            <strong>Review Intake</strong>: These transactions were auto-detected but require
                            categorization or confirmation before affecting your balance.
                        </div>
                    </div>

                    <div class="triage-filter-bar mb-4">
                        <div class="triage-search-box">
                            <span class="search-icon-mini">🔍</span>
                            <input type="text" v-model="triageSearchQuery"
                                placeholder="Search by merchant, ID or amount..." class="triage-search-input-premium">
                        </div>

                        <div class="source-toggle-group">
                            <button class="source-chip" :class="{ active: triageSourceFilter === 'ALL' }"
                                @click="triageSourceFilter = 'ALL'">All Sources</button>
                            <button class="source-chip" :class="{ active: triageSourceFilter === 'SMS' }"
                                @click="triageSourceFilter = 'SMS'">SMS</button>
                            <button class="source-chip" :class="{ active: triageSourceFilter === 'EMAIL' }"
                                @click="triageSourceFilter = 'EMAIL'">Email</button>
                        </div>
                    </div>

                    <div class="bulk-action-bar-triage mb-4 flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <label class="flex items-center gap-2 cursor-pointer text-xs font-bold text-muted">
                                <input type="checkbox" @change="toggleSelectAllTriage"
                                    :checked="selectedTriageIds.length === filteredTriageTransactions.length && filteredTriageTransactions.length > 0"
                                    class="rounded border-gray-300 text-indigo-600" />
                                Select All Filtered
                            </label>
                            <button v-if="selectedTriageIds.length > 0" @click="handleBulkRejectTriage"
                                class="bg-rose-50 text-rose-600 px-3 py-1 rounded-lg text-xs font-bold flex items-center gap-2">
                                🗑️ Discard {{ selectedTriageIds.length }}
                            </button>
                        </div>
                        <button @click="fetchTriage(true)" class="btn-icon-circle-small">🔄</button>
                    </div>

                    <div class="triage-grid">
                        <div v-for="txn in filteredTriageTransactions" :key="txn.id" class="glass-card triage-card"
                            :class="[txn.amount < 0 ? 'debit-theme' : 'credit-theme', { 'is-transfer-active': txn.is_transfer, 'selected': selectedTriageIds.includes(txn.id) }]">
                            <div class="triage-card-header">
                                <div class="header-left">
                                    <input type="checkbox" v-model="selectedTriageIds" :value="txn.id" class="mr-2" />
                                    <span class="source-tag" :class="txn.source.toLowerCase()">{{ txn.source }}</span>
                                    <span v-if="txn.is_ai_parsed" class="ai-badge-mini pulse"
                                        title="Extracted using Gemini AI">✨ AI Verified</span>
                                    <span v-if="txn.is_transfer" class="transfer-badge-mini"
                                        title="Auto-detected as internal transfer">🔄 Self-Transfer</span>
                                </div>
                                <span class="triage-date">{{ formatDate(txn.date).day }} <span class="date-sep">•</span>
                                    {{ formatDate(txn.date).meta }}</span>
                            </div>

                            <div class="triage-card-body">
                                <div class="triage-main-content">
                                    <div class="triage-amount-display" :class="txn.amount < 0 ? 'expense' : 'income'">
                                        <!-- Symbol removed as formatAmount includes it -->
                                        <div class="amount-val">{{ formatAmount(Math.abs(txn.amount)) }}</div>
                                        <div class="amount-indicator">{{ txn.amount < 0 ? 'Debit' : 'Credit' }}</div>
                                        </div>

                                        <div class="triage-details-info">
                                            <h3 class="triage-title">{{ txn.recipient || txn.description }}</h3>
                                            <div class="triage-account-info">
                                                <span class="acc-indicator"></span>
                                                {{ getAccountName(txn.account_id) }}
                                            </div>
                                        </div>
                                    </div>

                                    <div class="triage-meta-pills">
                                        <div class="meta-pill" v-if="txn.description">
                                            <span class="pill-icon">📝</span> {{ txn.description }}
                                        </div>
                                        <div class="meta-pill" v-if="txn.external_id">
                                            <span class="pill-icon">🆔</span> {{ txn.external_id }}
                                        </div>
                                        <div class="meta-pill highlight" v-if="txn.balance">
                                            <span class="pill-icon">💰</span> Bal: ₹{{ txn.balance.toFixed(2) }}
                                        </div>
                                    </div>

                                    <div v-if="txn.raw_message" class="triage-raw-box">
                                        <div class="raw-label">Origin Message</div>
                                        <div class="raw-content-text">{{ txn.raw_message }}</div>
                                    </div>
                                </div>

                                <div class="triage-card-actions">
                                    <div class="action-top-row">
                                        <div class="triage-input-group">
                                            <div class="toggle-control">
                                                <label class="premium-switch">
                                                    <input type="checkbox" v-model="txn.is_transfer"
                                                        @change="txn.exclude_from_reports = txn.is_transfer">
                                                    <span class="premium-slider"></span>
                                                </label>
                                                <span class="toggle-text">{{ txn.is_transfer ? 'Internal Transfer' :
                                                    'Expense/Income' }}</span>
                                            </div>

                                            <div class="toggle-control">
                                                <label class="premium-switch">
                                                    <input type="checkbox" v-model="txn.exclude_from_reports">
                                                    <span class="premium-slider"
                                                        style="background-color: #fee2e2;"></span>
                                                </label>
                                                <span class="toggle-text" style="color: #991b1b;">Exclude from
                                                    Reports</span>
                                            </div>

                                            <div class="select-container">
                                                <CustomSelect v-if="txn.is_transfer" v-model="txn.to_account_id"
                                                    :options="accountOptions.filter(a => a.value !== txn.account_id)"
                                                    :placeholder="txn.amount < 0 ? 'To Account (Tracked)' : 'From Account (Tracked)'"
                                                    class="triage-select-premium" />
                                                <CustomSelect v-else v-model="txn.category" :options="categoryOptions"
                                                    placeholder="Assign Category" class="triage-select-premium" />
                                            </div>
                                        </div>
                                    </div>

                                    <div class="action-bottom-row">
                                        <button @click="rejectTriage(txn.id)"
                                            class="btn-triage-secondary">Discard</button>

                                        <div class="approval-cluster">
                                            <button @click="approveTriage(txn)" class="btn-triage-primary">
                                                Confirm Entry
                                                <span class="btn-shimmer"></span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="triagePagination.total === 0" class="empty-state-triage">
                            <div class="empty-glow-icon">✨</div>
                            <h3>Inbox zero!</h3>
                            <p>No new transactions waiting for review.</p>
                        </div>

                        <!-- Triage Pagination & Page Size -->
                        <div v-if="triagePagination.total > 0"
                            class="mt-6 flex items-center justify-between border-t border-gray-100 pt-6">
                            <div class="flex items-center gap-4">
                                <span class="text-[10px] text-muted font-mono">
                                    {{ triagePagination.skip + 1 }}–{{ Math.min(triagePagination.skip +
                                        triagePagination.limit,
                                        triagePagination.total) }} of {{ triagePagination.total }}
                                </span>
                                <div class="flex items-center gap-2">
                                    <span class="text-[10px] text-muted uppercase font-bold tracking-wider">Size:</span>
                                    <select v-model="triagePagination.limit"
                                        @change="triagePagination.skip = 0; fetchTriage()"
                                        class="text-[10px] bg-white border border-gray-200 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-bold text-slate-700">
                                        <option :value="10">10</option>
                                        <option :value="20">20</option>
                                        <option :value="50">50</option>
                                        <option :value="100">100</option>
                                    </select>
                                </div>
                            </div>
                            <div class="flex items-center gap-1" v-if="triagePagination.total > triagePagination.limit">
                                <button @click="triagePagination.skip -= triagePagination.limit; fetchTriage()"
                                    :disabled="triagePagination.skip === 0" class="btn-pagination-compact">Prev</button>
                                <button @click="triagePagination.skip += triagePagination.limit; fetchTriage()"
                                    :disabled="triagePagination.skip + triagePagination.limit >= triagePagination.total"
                                    class="btn-pagination-compact">Next</button>
                            </div>
                        </div>
                    </div>

                    <!-- Training Area -->
                    <div v-if="activeTriageSubTab === 'training'">
                        <div class="alert-info-glass mb-4 training-alert">
                            <div class="alert-icon">🤖</div>
                            <div class="alert-text">
                                <strong>Interactive Training</strong>: These messages look like transactions but could
                                not be parsed. Label them to help the system learn!
                            </div>
                        </div>

                        <div class="bulk-action-bar-training mb-4 flex items-center justify-between">
                            <div class="flex items-center gap-4">
                                <label
                                    class="flex items-center gap-2 cursor-pointer text-xs font-bold text-amber-800/60">
                                    <input type="checkbox" @change="toggleSelectAllTraining"
                                        :checked="selectedTrainingIds.length === unparsedMessages.length && unparsedMessages.length > 0"
                                        class="rounded border-amber-300 text-amber-600" />
                                    Select All Current
                                </label>
                                <button v-if="selectedTrainingIds.length > 0" @click="handleBulkDismissTraining"
                                    class="bg-amber-100 text-amber-800 px-3 py-1 rounded-lg text-xs font-bold flex items-center gap-2">
                                    🗑️ Dismiss {{ selectedTrainingIds.length }}
                                </button>
                            </div>
                            <button @click="fetchTriage(true)" class="btn-icon-circle-small amber-themed">🔄</button>
                        </div>

                        <div class="triage-grid">
                            <div v-for="msg in unparsedMessages" :key="msg.id"
                                class="glass-card triage-card training-theme"
                                :class="{ 'selected': selectedTrainingIds.includes(msg.id) }">
                                <div class="triage-card-header">
                                    <div class="header-left">
                                        <input type="checkbox" v-model="selectedTrainingIds" :value="msg.id"
                                            class="mr-2" />
                                        <span class="source-tag" :class="msg.source.toLowerCase()">{{ msg.source
                                        }}</span>
                                        <span class="ai-badge-mini"
                                            style="background: #fef3c7; color: #92400e; border-color: #f59e0b;">🤖 Needs
                                            Training</span>
                                    </div>
                                    <span class="triage-date">{{ formatDate(msg.created_at).day }}</span>
                                </div>

                                <div class="triage-card-body">
                                    <div class="training-content-premium">
                                        <div class="training-header">
                                            <div class="training-sender" v-if="msg.sender">
                                                <span class="label">Sender:</span> {{ msg.sender }}
                                            </div>
                                            <div class="training-subject" v-if="msg.subject">
                                                <span class="label">Subject:</span> {{ msg.subject }}
                                            </div>
                                        </div>
                                        <pre class="training-raw-preview-premium">{{ msg.raw_content }}</pre>
                                    </div>
                                </div>

                                <div class="triage-card-actions">
                                    <div class="action-bottom-row">
                                        <button @click="dismissTraining(msg.id)"
                                            class="btn-triage-secondary">Dismiss</button>
                                        <button @click="startLabeling(msg)" class="btn-triage-primary">
                                            Label Fields
                                            <span class="btn-shimmer"></span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="trainingPagination.total === 0" class="empty-state-triage">
                            <div class="empty-glow-icon">🛡️</div>
                            <h3>All clear!</h3>
                            <p>No unparsed messages waiting for training.</p>
                        </div>

                        <!-- Training Area Pagination & Page Size -->
                        <div v-if="trainingPagination.total > 0"
                            class="mt-6 flex items-center justify-between border-t border-gray-100 pt-6">
                            <div class="flex items-center gap-4">
                                <span class="text-[10px] text-muted font-mono">
                                    {{ trainingPagination.skip + 1 }}–{{ Math.min(trainingPagination.skip +
                                        trainingPagination.limit, trainingPagination.total) }} of {{
                                        trainingPagination.total }}
                                </span>
                                <div class="flex items-center gap-2">
                                    <span class="text-[10px] text-muted uppercase font-bold tracking-wider">Page
                                        Size:</span>
                                    <select v-model="trainingPagination.limit"
                                        @change="trainingPagination.skip = 0; fetchTriage()"
                                        class="text-[10px] bg-white border border-amber-200 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-amber-500 font-bold text-amber-800">
                                        <option :value="10">10</option>
                                        <option :value="20">20</option>
                                        <option :value="50">50</option>
                                        <option :value="100">100</option>
                                        <option :value="200">200</option>
                                        <option :value="500">500</option>
                                    </select>
                                </div>
                            </div>
                            <div class="flex items-center gap-1"
                                v-if="trainingPagination.total > trainingPagination.limit">
                                <button @click="trainingPagination.skip -= trainingPagination.limit; fetchTriage()"
                                    :disabled="trainingPagination.skip === 0"
                                    class="btn-pagination-compact amber">Prev</button>
                                <button @click="trainingPagination.skip += trainingPagination.limit; fetchTriage()"
                                    :disabled="trainingPagination.skip + trainingPagination.limit >= trainingPagination.total"
                                    class="btn-pagination-compact amber">Next</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Heatmap View -->
            <div v-if="activeTab === 'heatmap'" class="heatmap-view animate-in">
                <div v-if="loadingHeatmap" class="loading-overlay">
                    <div class="spinner"></div>
                    Loading Map Data...
                </div>
                <SpendingHeatmap :data="heatmapData" />
                <div class="heatmap-footer mt-4">
                    <p class="text-xs text-muted">Showing spending density based on transaction geolocation. Only
                        transactions with coordinates are displayed.</p>
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
                            <CustomSelect v-model="form.account_id" :options="accountOptions"
                                placeholder="Select Account" />
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div class="form-group" style="margin-bottom: 0;">
                                <label class="form-label">Amount</label>
                                <input type="number" step="0.01" v-model="form.amount" class="form-input" required
                                    placeholder="-50.00" />
                            </div>
                            <div class="form-group" style="margin-bottom: 0;">
                                <label class="form-label">Date</label>
                                <input type="datetime-local" v-model="form.date" class="form-input" required />
                            </div>
                        </div>

                        <div class="form-group">
                            <label class="form-label">Description</label>
                            <input v-model="form.description" class="form-input" required
                                placeholder="e.g. Grocery shopping" />
                        </div>

                        <div class="form-group">
                            <div
                                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <label class="form-label" style="margin-bottom: 0;">Category & Options</label>
                                <div v-if="currentCategoryBudget" class="budget-preview-tag"
                                    :class="{ 'danger': currentCategoryBudget.remaining < 0 }">
                                    <span class="dot"></span>
                                    {{ formatAmount(currentCategoryBudget.remaining) }} left
                                </div>
                            </div>

                            <!-- Options Panel -->
                            <div
                                style="display: flex; flex-direction: column; gap: 0.75rem; padding: 0.875rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0.75rem; margin-bottom: 1rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-size: 0.8125rem; font-weight: 600; color: #475569;">Is internal
                                        transfer?</span>
                                    <div class="toggle-control" style="min-width: unset;">
                                        <label class="premium-switch">
                                            <input type="checkbox" v-model="form.is_transfer">
                                            <span class="premium-slider"></span>
                                        </label>
                                        <span class="toggle-text" style="min-width: 40px; text-align: right;">{{
                                            form.is_transfer ? 'Yes' : 'No' }}</span>
                                    </div>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-size: 0.8125rem; font-weight: 600; color: #991b1b;">Exclude from
                                        reports?</span>
                                    <div class="toggle-control" style="min-width: unset;">
                                        <label class="premium-switch">
                                            <input type="checkbox" v-model="form.exclude_from_reports">
                                            <span class="premium-slider"
                                                style="background-color: #fee2e2; border: 1px solid #fecaca;"></span>
                                        </label>
                                        <span class="toggle-text"
                                            style="color: #991b1b; min-width: 40px; text-align: right;">{{
                                                form.exclude_from_reports ? 'Yes' : 'No' }}</span>
                                    </div>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-size: 0.8125rem; font-weight: 600; color: #0369a1;">Is EMI
                                        Payment?</span>
                                    <div class="toggle-control" style="min-width: unset;">
                                        <label class="premium-switch">
                                            <input type="checkbox" v-model="form.is_emi">
                                            <span class="premium-slider"
                                                style="background-color: #e0f2fe; border: 1px solid #bae6fd;"></span>
                                        </label>
                                        <span class="toggle-text"
                                            style="color: #0369a1; min-width: 40px; text-align: right;">{{ form.is_emi ?
                                                'Yes' : 'No' }}</span>
                                    </div>
                                </div>
                                <div v-if="form.is_emi" class="mt-2">
                                    <label class="text-xs font-bold text-gray-500 uppercase">Select Loan</label>
                                    <CustomSelect v-model="form.loan_id" :options="loanOptions"
                                        placeholder="Link to Loan" />
                                </div>
                            </div>

                            <div v-if="form.is_transfer">
                                <label class="form-label">Linked Account</label>
                                <CustomSelect v-model="form.to_account_id"
                                    :options="accountOptions.filter(a => a.value !== form.account_id)"
                                    :placeholder="!form.amount || form.amount < 0 ? 'To Account' : 'From Account'" />

                                <!-- Match Finder -->
                                <div v-if="form.to_account_id && form.amount"
                                    class="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                    <div class="flex justify-between items-center mb-2">
                                        <span class="text-xs font-semibold uppercase text-gray-500">Transaction
                                            Matcher</span>
                                        <button type="button" @click="findMatches"
                                            class="text-xs text-blue-600 hover:text-blue-800"
                                            :disabled="isSearchingMatches">
                                            {{ isSearchingMatches ? 'Searching...' : 'Find Matches 🔍' }}
                                        </button>
                                    </div>

                                    <div v-if="potentialMatches.length > 0" class="space-y-2">
                                        <div v-for="match in potentialMatches" :key="match.id"
                                            class="p-2 border rounded cursor-pointer text-sm bg-white hover:bg-blue-50 transition-colors"
                                            :class="form.linked_transaction_id === match.id ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'"
                                            @click="selectMatch(match)">
                                            <div class="flex justify-between font-medium">
                                                <span>{{ new Date(match.date).toLocaleDateString() }}</span>
                                                <span :class="match.amount > 0 ? 'text-green-600' : 'text-red-600'">
                                                    {{ formatAmount(match.amount) }}
                                                </span>
                                            </div>
                                            <div class="text-gray-600 truncate">{{ match.description }}</div>
                                        </div>
                                    </div>
                                    <div v-else-if="matchesSearched" class="text-xs text-center text-gray-500 py-2">
                                        No matches found around this date.
                                    </div>
                                </div>
                            </div>
                            <div v-else>
                                <label class="form-label">Category</label>
                                <CustomSelect v-model="form.category" :options="categoryOptions"
                                    placeholder="Select Category" allow-new />
                            </div>
                        </div>

                        <div class="form-group" style="border-top: 1px solid #efefef; padding-top: 1rem;">
                            <label class="form-label">Expense Group (Event/Project)</label>
                            <CustomSelect v-model="form.expense_group_id"
                                :options="[{ label: 'None', value: '' }, ...expenseGroupOptions]"
                                placeholder="Link to Expense Group" />
                            <p class="text-[10px] text-muted mt-1 italic">Groups help track spending for specific events
                                like vacations or projects.</p>
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


            <!-- Smart Categorization / Exclusion Prompt -->
            <div v-if="showSmartPrompt" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 450px;">
                    <div class="modal-header">
                        <h2 class="modal-title">
                            {{ smartPromptData.excludeFromReports ? 'Auto-Exclude Rule 🙈' : 'Smart Categorization 🧠'
                            }}
                        </h2>
                        <button class="btn-icon" @click="showSmartPrompt = false">✕</button>
                    </div>
                    <div style="padding: 1.5rem;">
                        <p v-if="smartPromptData.excludeFromReports"
                            style="margin-bottom: 1.25rem; color: #4b5563; line-height: 1.5;">
                            You marked <strong>{{ smartPromptData.pattern }}</strong> as <strong>Hidden</strong>
                            <span v-if="smartPromptData.category && smartPromptData.category !== 'Uncategorized'">
                                and categorized as <strong>{{ smartPromptData.category }}</strong></span>.
                            Do you want to update the rule to always apply this?
                        </p>
                        <p v-else style="margin-bottom: 1.25rem; color: #4b5563; line-height: 1.5;">
                            You categorized <strong>{{ smartPromptData.pattern }}</strong> as <strong>{{
                                smartPromptData.category }}</strong>.
                        </p>

                        <div class="smart-options">
                            <label class="smart-option-item" v-if="smartPromptData.count > 0">
                                <input type="checkbox" v-model="smartPromptData.applyToSimilar" class="checkbox-input">
                                <span>
                                    {{ smartPromptData.excludeFromReports ? 'Exclude' : 'Apply to' }}
                                    <strong>{{ smartPromptData.count }}</strong> similar
                                    {{ smartPromptData.excludeFromReports ? '' : 'uncategorized' }}
                                    transactions
                                </span>
                            </label>

                            <label class="smart-option-item">
                                <input type="checkbox" v-model="smartPromptData.createRule" class="checkbox-input">
                                <span v-if="smartPromptData.excludeFromReports">
                                    Always <strong>hide</strong>
                                    <span
                                        v-if="smartPromptData.category && smartPromptData.category !== 'Uncategorized'">
                                        and categorize as <strong>{{ smartPromptData.category }}</strong>
                                    </span>
                                    transactions from <strong>{{ smartPromptData.pattern }}</strong> in future
                                    (Update/Create Rule)
                                </span>
                                <span v-else>
                                    Always categorize <strong>{{ smartPromptData.pattern }}</strong> as <strong>{{
                                        smartPromptData.category }}</strong> in future
                                </span>
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
                            Are you sure you want to delete <strong>{{ selectedIds.size }}</strong> selected
                            transactions? This action cannot be undone.
                        </p>
                        <div class="modal-footer"
                            style="padding: 0; border: none; background: transparent; justify-content: center; gap: 1rem;">
                            <button class="btn btn-outline" @click="showDeleteConfirm = false">Cancel</button>
                            <button class="btn btn-danger" @click="confirmDelete"
                                style="background: #ef4444; color: white; border: none;">Delete</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Triage Discard Confirmation Modal -->
            <div v-if="showDiscardConfirm" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 400px;">
                    <div class="modal-header">
                        <h2 class="modal-title">Discard Transaction</h2>
                        <button class="btn-icon"
                            @click="showDiscardConfirm = false; createIgnoreRule = false">✕</button>
                    </div>
                    <div style="padding: 1.5rem; text-align: center;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">♻️</div>
                        <p style="color: #4b5563; margin-bottom: 1.5rem;">
                            Discard this potential transaction? It will be removed from your review list.
                        </p>

                        <div
                            style="margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; font-size: 0.875rem; color: #6b7280; background: #f9fafb; padding: 0.75rem; border-radius: 0.5rem;">
                            <input type="checkbox" v-model="createIgnoreRule" id="ignoreFuture"
                                class="rounded border-gray-300 text-rose-600 focus:ring-rose-500" />
                            <label for="ignoreFuture" class="cursor-pointer font-medium text-gray-700">Don't show
                                similar messages again</label>
                        </div>

                        <div class="modal-footer"
                            style="padding: 0; border: none; background: transparent; justify-content: center; gap: 1rem;">
                            <button class="btn btn-outline"
                                @click="showDiscardConfirm = false; createIgnoreRule = false">Keep It</button>
                            <button class="btn-danger" @click="confirmDiscard"
                                style="background: #ef4444; color: white; border: none; padding: 0.625rem 1.5rem; border-radius: 0.5rem; cursor: pointer; font-weight: 600;">Discard</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Training Discard Confirmation Modal -->
            <div v-if="showTrainingDiscardConfirm" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 400px;">
                    <div class="modal-header">
                        <h2 class="modal-title">Dismiss Message</h2>
                        <button class="btn-icon"
                            @click="showTrainingDiscardConfirm = false; createIgnoreRule = false">✕</button>
                    </div>
                    <div style="padding: 1.5rem; text-align: center;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🛡️</div>
                        <p style="color: #4b5563; margin-bottom: 1.5rem;">
                            {{ trainingIdToDiscard ? 'Dismiss this unparsed message?' : `Dismiss
                            ${selectedTrainingIds.length} unparsed messages?` }}
                        </p>

                        <div
                            style="margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; font-size: 0.875rem; color: #6b7280; background: #f9fafb; padding: 0.75rem; border-radius: 0.5rem;">
                            <input type="checkbox" v-model="createIgnoreRule" id="ignoreFutureTraining"
                                class="rounded border-gray-300 text-amber-600 focus:ring-amber-500" />
                            <label for="ignoreFutureTraining" class="cursor-pointer font-medium text-gray-700">Don't
                                show similar messages again</label>
                        </div>

                        <div class="modal-footer"
                            style="padding: 0; border: none; background: transparent; justify-content: center; gap: 1rem;">
                            <button class="btn btn-outline"
                                @click="showTrainingDiscardConfirm = false; createIgnoreRule = false">Cancel</button>
                            <button class="btn-primary" @click="handleConfirmGlobalTrainingDismiss"
                                style="background: #f59e0b; color: white; border: none; padding: 0.625rem 1.5rem; border-radius: 0.5rem; cursor: pointer; font-weight: 600;">Dismiss</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Interactive Labeling Modal -->
            <div v-if="showLabelForm" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 750px;">
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

                        <form @submit.prevent="handleLabelSubmit" class="labeling-form">
                            <div class="form-grid-2">
                                <div class="form-group">
                                    <label class="form-label">Amount (₹)</label>
                                    <input type="number" v-model="labelForm.amount" class="form-input" required
                                        step="0.01">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Date</label>
                                    <input type="datetime-local" v-model="labelForm.date" class="form-input" required>
                                </div>
                            </div>

                            <div class="form-grid-2">
                                <div class="form-group">
                                    <label class="form-label">Type</label>
                                    <div class="flex gap-4">
                                        <label class="flex items-center gap-2 cursor-pointer">
                                            <input type="radio" v-model="labelForm.type" value="DEBIT"
                                                class="text-indigo-600 focus:ring-indigo-500">
                                            <span class="text-xs font-semibold text-gray-700">Debit</span>
                                        </label>
                                        <label class="flex items-center gap-2 cursor-pointer">
                                            <input type="radio" v-model="labelForm.type" value="CREDIT"
                                                class="text-green-600 focus:ring-green-500">
                                            <span class="text-xs font-semibold text-gray-700">Credit</span>
                                        </label>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Account Mask</label>
                                    <input type="text" v-model="labelForm.account_mask" class="form-input"
                                        placeholder="e.g. 1234" required maxlength="4">
                                </div>
                            </div>

                            <div class="form-grid-2">
                                <div class="form-group">
                                    <label class="form-label">Recipient / Merchant</label>
                                    <input type="text" v-model="labelForm.recipient" class="form-input"
                                        placeholder="e.g. Starbucks">
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Reference ID (Optional)</label>
                                    <input type="text" v-model="labelForm.ref_id" class="form-input"
                                        placeholder="UTR / TXN ID">
                                </div>
                            </div>

                            <div class="form-group">
                                <label class="form-label">Category</label>
                                <CustomSelect v-model="labelForm.category" :options="categoryOptions"
                                    placeholder="Assign Category" />
                            </div>

                            <div class="form-group check-group" style="margin-top: 0.5rem; background: #fef2f2;">
                                <input type="checkbox" id="excludeReport" v-model="labelForm.exclude_from_reports">
                                <label for="excludeReport" style="color: #991b1b;">Exclude from reports &
                                    analytics</label>
                            </div>

                            <div class="form-group check-group" style="margin-top: 0.5rem;">
                                <input type="checkbox" id="genPattern" v-model="labelForm.generate_pattern">
                                <label for="genPattern">Learn this pattern for future messages</label>
                            </div>

                            <div class="modal-footer" style="padding: 1.5rem 0 0 0; background: transparent;">
                                <button type="button" class="btn btn-outline"
                                    @click="showLabelForm = false">Cancel</button>
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

.training-sender,
.training-subject {
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
    gap: 1rem;
    padding: 1rem;
}

.labeling-raw {
    background: #f9fafb;
    border-radius: 0.75rem;
    padding: 0.75rem;
    border: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
}

.raw-content-box {
    background: white;
    padding: 0.875rem;
    border-radius: 0.5rem;
    font-family: monospace;
    font-size: 0.75rem;
    white-space: pre-wrap;
    border: 1px solid #f3f4f6;
    flex-grow: 1;
    overflow-y: auto;
    max-height: 300px;
    color: #111827;
}

.raw-meta {
    margin-top: 1rem;
    font-size: 0.75rem;
    color: #6b7280;
}

.section-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 0.5rem;
    letter-spacing: 0.05em;
}

.labeling-form .form-group {
    margin-bottom: 0.75rem;
}

.labeling-form .form-label {
    font-size: 0.75rem;
    margin-bottom: 2px;
}

.labeling-form .form-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
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
    to {
        transform: rotate(360deg);
    }
}

/* Budget Preview Tag (Modal) */
.budget-preview-tag {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.125rem 0.625rem;
    background: #ecfdf5;
    color: #065f46;
    border-radius: 999px;
    font-size: 0.725rem;
    font-weight: 600;
    border: 1px solid #d1fae5;
    animation: slideInLeft 0.3s ease-out;
}

.budget-preview-tag.danger {
    background: #fef2f2;
    color: #991b1b;
    border-color: #fee2e2;
}

.budget-preview-tag .dot {
    width: 5px;
    height: 5px;
    background: currentColor;
    border-radius: 50%;
}

@keyframes slideInLeft {
    from {
        opacity: 0;
        transform: translateX(-10px);
    }

    to {
        opacity: 1;
        transform: translateX(0);
    }
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

.list-search-container {
    position: relative;
    display: flex;
    align-items: center;
}

.search-icon-small {
    position: absolute;
    left: 0.75rem;
    font-size: 0.8rem;
    color: #9ca3af;
}

.list-search-input {
    padding: 0.45rem 0.75rem 0.45rem 2rem;
    font-size: 0.8125rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    background: white;
    width: 220px;
    outline: none;
    transition: all 0.2s;
}

.list-search-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.category-filter-select {
    min-width: 180px;
}

.filter-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}

.filter-divider {
    width: 1px;
    height: 24px;
    background: #e5e7eb;
    margin: 0 0.25rem;
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
    from {
        opacity: 0;
        transform: translateX(-10px);
    }

    to {
        opacity: 1;
        transform: translateX(0);
    }
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

.income .card-icon {
    background: #ecfdf5;
}

.expense .card-icon {
    background: #fef2f2;
}

.net .card-icon {
    background: #eff6ff;
}

.net.is-negative .card-icon {
    background: #fff7ed;
}

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

.income .card-value {
    color: #059669;
}

.expense .card-value {
    color: #dc2626;
}

.net.is-negative .card-value {
    color: #d97706;
}

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
    background: #4f46e5;
    border-radius: 9999px;
    transition: width 0.3s ease;
}

.type-bar {
    background: #8b5cf6;
}

/* Credit Utilization Box */
.credit-preview-box {
    background: #f8fafc;
    padding: 1rem;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
}

.credit-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}

.credit-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
}

.credit-val {
    font-size: 0.8125rem;
    font-weight: 700;
    color: #1e293b;
}

.credit-bar-container {
    height: 0.5rem;
    background: #e2e8f0;
    border-radius: 999px;
    margin-bottom: 0.75rem;
    overflow: hidden;
}

.credit-bar-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.3s ease;
}

.credit-bar-fill.safe {
    background: #10b981;
}

.credit-bar-fill.warning {
    background: #f59e0b;
}

.credit-bar-fill.danger {
    background: #ef4444;
}

.credit-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
}

.mt-6 {
    margin-top: 1.5rem;
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

.pattern-bar-fill.weekday {
    background: #4f46e5;
}

.pattern-bar-fill.weekend {
    background: #f59e0b;
}

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



/* --- Premium Triage Card Styling --- */
.triage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 1.5rem;
}

.triage-card {
    display: flex;
    flex-direction: column;
    padding: 0 !important;
    overflow: visible;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(0, 0, 0, 0.05);
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(12px);
    z-index: 1;
    /* Establish base level */
}

.triage-card:hover,
.triage-card:focus-within {
    z-index: 50;
    /* Rise above neighbors when interactive */
}

.triage-card:hover {
    transform: translateY(-6px) scale(1.01);
    box-shadow: 0 16px 32px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.04);
}

.triage-card.is-transfer-active {
    border-color: rgba(99, 102, 241, 0.3);
    background: linear-gradient(to bottom right, rgba(255, 255, 255, 0.95), rgba(238, 242, 255, 0.5));
}

.triage-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.03);
    background: rgba(0, 0, 0, 0.01);
    border-top-left-radius: 1.25rem;
    border-top-right-radius: 1.25rem;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.triage-date {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
}

.date-sep {
    opacity: 0.3;
    margin: 0 4px;
}

.triage-card-body {
    padding: 1.25rem;
    flex-grow: 1;
}

.triage-main-content {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-bottom: 1.25rem;
}

.triage-amount-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 110px;
    padding: 1rem;
    border-radius: 16px;
    position: relative;
}

.currency-symbol {
    font-size: 0.875rem;
    opacity: 0.6;
    margin-bottom: -4px;
}

.amount-val {
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.amount-indicator {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}

/* Themes */
.debit-theme .triage-amount-display {
    background: rgba(239, 68, 68, 0.08);
    color: #dc2626;
}

.credit-theme .triage-amount-display {
    background: rgba(16, 185, 129, 0.08);
    color: #059669;
}

.triage-details-info {
    flex-grow: 1;
}

.triage-title {
    font-size: 1.125rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
    color: var(--color-text-primary);
}

.triage-account-info {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-muted);
}

.acc-indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.5;
}

.triage-meta-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1.25rem;
}

.meta-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
}

.meta-pill.highlight {
    background: rgba(99, 102, 241, 0.06);
    color: #4f46e5;
}

.triage-raw-box {
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 10px;
    border: 1px dashed rgba(0, 0, 0, 0.05);
}

.raw-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin-bottom: 4px;
}

.raw-content-text {
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    color: var(--color-text-muted);
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-all;
}

.triage-card-actions {
    padding: 1rem 1.25rem;
    background: rgba(0, 0, 0, 0.015);
    border-top: 1px solid rgba(0, 0, 0, 0.03);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    border-bottom-left-radius: 1.25rem;
    border-bottom-right-radius: 1.25rem;
}

.action-top-row {
    display: flex;
    align-items: center;
}

.triage-input-group {
    display: flex;
    align-items: center;
    gap: 1rem;
    width: 100%;
}

.toggle-control {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 140px;
}

.toggle-text {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
}

.select-container {
    flex-grow: 1;
}

.triage-select-premium {
    width: 100%;
}

.triage-select-premium :deep(.select-trigger) {
    background: white;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
    padding: 0.625rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.triage-select-premium :deep(.select-trigger:focus-within) {
    border-color: #6366f1;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
}

.action-bottom-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Premium Buttons & Switches */
.btn-triage-primary {
    padding: 0.625rem 1.5rem;
    background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 0.875rem;
    font-weight: 700;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}

.btn-triage-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(79, 70, 229, 0.4);
}

.btn-triage-primary:active {
    transform: translateY(0);
}

.btn-shimmer {
    position: absolute;
    top: 0;
    left: -100%;
    width: 50%;
    height: 100%;
    background: linear-gradient(to right,
            rgba(255, 255, 255, 0) 0%,
            rgba(255, 255, 255, 0.2) 50%,
            rgba(255, 255, 255, 0) 100%);
    transform: skewX(-25deg);
    transition: none;
}

.btn-triage-primary:hover .btn-shimmer {
    animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
    100% {
        left: 150%;
    }
}

.approval-cluster {
    display: flex;
    align-items: center;
    gap: 1.25rem;
}

.btn-triage-secondary {
    background: none;
    border: none;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.2s;
}

.btn-triage-secondary:hover {
    color: #dc2626;
}

.cache-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
}

.cache-checkbox input {
    display: none;
}

.checkbox-box {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.04);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.checkbox-text {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
}

.cache-checkbox input:checked+.checkbox-box {
    background: #eef2ff;
    color: #4f46e5;
    transform: scale(1.1);
}

.checkbox-icon {
    font-size: 1rem;
    filter: grayscale(1);
    opacity: 0.5;
}

.cache-checkbox input:checked+.checkbox-box .checkbox-icon {
    filter: grayscale(0);
    opacity: 1;
}

/* Premium Slider */
.premium-switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
}

.premium-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.premium-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #e2e8f0;
    transition: .4s;
    border-radius: 34px;
}

.premium-slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

input:checked+.premium-slider {
    background-color: #4f46e5;
}

input:checked+.premium-slider:before {
    transform: translateX(18px);
}

/* Badges */
.transfer-badge-mini {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: #ecfdf5;
    color: #059669;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.65rem;
    font-weight: 700;
    border: 1px solid rgba(5, 150, 105, 0.2);
}

.pulse {
    animation: pulse-animation 2s infinite;
}

@keyframes pulse-animation {
    0% {
        transform: scale(1);
        opacity: 1;
    }

    50% {
        transform: scale(1.05);
        opacity: 0.8;
    }

    100% {
        transform: scale(1);
        opacity: 1;
    }
}

/* Transfer Active State Decoration */
.is-transfer-active.triage-card {
    border: 1px solid rgba(16, 185, 129, 0.2);
    box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.1);
}

.training-theme.triage-card {
    border-left: 4px solid #f59e0b;
}

.training-header {
    margin-bottom: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.training-sender,
.training-subject {
    font-size: 0.8rem;
    color: var(--color-text-primary);
    font-weight: 500;
}

.training-sender .label,
.training-subject .label {
    color: var(--color-text-muted);
    font-weight: 600;
    margin-right: 4px;
}

.training-raw-preview-premium {
    background: #1e293b;
    color: #e2e8f0;
    padding: 1rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    max-height: 120px;
    overflow-y: auto;
    border: 1px solid rgba(255, 255, 255, 0.1);
    line-height: 1.5;
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

.alert-icon {
    font-size: 1.25rem;
}

.alert-text {
    font-size: 0.875rem;
    color: #1e40af;
}

.ref-id-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: #eef2ff;
    /* Light Indigo */
    border: 1px solid #c7d2fe;
    border-radius: 100px;
    font-size: 10px;
    font-family: inherit;
    color: var(--color-text-muted);
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

/* --- Transfer & Toggle Logic CSS --- */
.approval-form {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.transfer-manual-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    white-space: nowrap;
}

.toggle-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
}

.rule-toggle {
    display: flex;
    align-items: center;
    cursor: pointer;
}

.rule-toggle input {
    display: none;
}

.rule-toggle label {
    cursor: pointer;
    font-size: 1rem;
    opacity: 0.3;
    transition: all 0.2s;
}

.rule-toggle input:checked+label {
    opacity: 1;
    transform: scale(1.2);
}

/* Switch UI */
.switch {
    position: relative;
    display: inline-block;
    width: 28px;
    height: 16px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #cbd5e1;
    -webkit-transition: .4s;
    transition: .4s;
}

.slider:before {
    position: absolute;
    content: "";
    height: 12px;
    width: 12px;
    left: 2px;
    bottom: 2px;
    background-color: white;
    -webkit-transition: .4s;
    transition: .4s;
}

input:checked+.slider {
    background-color: var(--brand-primary, #6366f1);
}

input:focus+.slider {
    box-shadow: 0 0 1px var(--brand-primary, #6366f1);
}

input:checked+.slider:before {
    -webkit-transform: translateX(12px);
    -ms-transform: translateX(12px);
    transform: translateX(12px);
}

.slider.round {
    border-radius: 34px;
}

.slider.round:before {
    border-radius: 50%;
}

.amount-cell.is-transfer {
    color: #64748b;
    /* Slate 500 */
    background: #f1f5f9;
    font-style: italic;
}

.triage-card.selected {
    border: 1px solid var(--brand-primary, #6366f1);
    background: rgba(99, 102, 241, 0.05);
}

.triage-filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1.5rem;
    background: white;
    padding: 0.75rem 1rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.triage-search-box {
    position: relative;
    flex: 1;
    max-width: 400px;
}

.search-icon-mini {
    position: absolute;
    left: 0.875rem;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0.4;
    font-size: 0.875rem;
}

.triage-search-input-premium {
    width: 100%;
    padding: 0.625rem 0.625rem 0.625rem 2.25rem;
    border: 1px solid #f3f4f6;
    background: #f9fafb;
    border-radius: 0.75rem;
    font-size: 0.8125rem;
    outline: none;
    transition: all 0.2s;
}

.triage-search-input-premium:focus {
    background: white;
    border-color: #4f46e5;
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.source-toggle-group {
    display: flex;
    gap: 0.25rem;
    background: #f3f4f6;
    padding: 0.25rem;
    border-radius: 0.625rem;
}

.source-chip {
    padding: 0.375rem 0.875rem;
    border: none;
    background: transparent;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
}

.source-chip:hover:not(.active) {
    color: #111827;
}

.source-chip.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}
</style>
