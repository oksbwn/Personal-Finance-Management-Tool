<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import { useCurrency } from '@/composables/useCurrency'

const { formatAmount } = useCurrency()

const props = defineProps<{
    isOpen: boolean
}>()

const emit = defineEmits(['close', 'import-success'])

const notify = useNotificationStore()

// State
const step = ref(1)
const loading = ref(false)
const accounts = ref<any[]>([])
const selectedAccount = ref('')
const file = ref<File | null>(null)

// Step 2: Mapping
const mapping = ref({
    date: 'Date',
    description: 'Description',
    reference: '', // Optional
    balance: '', // Optional
    credit_limit: '', // Optional
    amount: 'Amount',
    mode: 'single' as 'single' | 'split'
})
const splitMapping = ref({
    debit: 'Debit',
    credit: 'Credit'
})
const csvHeaders = ref<string[]>([])
const detectedHeaderRow = ref(0)
const previewRows = ref<any[]>([])
const analyzing = ref(false)

// Step 3: Verification
const parsedTxns = ref<any[]>([])
const selectedTxns = ref<Set<number>>(new Set())

// Step 4: Results
const importResult = ref<any>(null)

async function fetchAccounts() {
    try {
        const res = await financeApi.getAccounts()
        accounts.value = res.data
    } catch (e) {
        notify.error("Failed to load accounts")
    }
}

const accountOptions = computed(() => accounts.value.map(a => ({ label: `${a.icon || '🏦'} ${a.name}`, value: a.id })))

// Watch open to load accounts
watch(() => props.isOpen, (val) => {
    if (val) {
        reset()
        fetchAccounts()
    }
})

// Watch account selection to load mapping
watch(selectedAccount, (newVal) => {
    if (newVal) {
        const acc = accounts.value.find(a => a.id === newVal)
        if (acc && acc.import_config) {
            try {
                const config = JSON.parse(acc.import_config)
                mapping.value = { ...mapping.value, ...config.mapping }
                splitMapping.value = { ...splitMapping.value, ...config.splitMapping }
                // Restore mode if saved
                if (config.mode) mapping.value.mode = config.mode

                notify.info("Loaded saved mapping")
            } catch (e) {
                console.error("Failed to parse import config", e)
            }
        }
    }
})

async function handleFileUpload(event: Event) {
    const target = event.target as HTMLInputElement
    if (target.files && target.files[0]) {
        file.value = target.files[0]
        analyzing.value = true

        try {
            const formData = new FormData()
            formData.append('file', file.value)

            const res = await financeApi.analyzeCsv(formData)
            const analysis = res.data

            csvHeaders.value = analysis.headers
            detectedHeaderRow.value = analysis.header_row_index
            previewRows.value = analysis.preview

            notify.success(`Detected headers on row ${analysis.header_row_index + 1}`)

            // Auto-Map if not loaded from config
            // Simple heuristic to pre-fill common names if not already set (or if set to default)
            // (Skipping complex auto-map for now, trust Saved Config first, then user)

        } catch (e) {
            notify.error("Failed to analyze file. Please check format.")
            console.error(e)
        } finally {
            analyzing.value = false
        }
    }
}

async function parseFile() {
    if (!file.value) return notify.error("Please select a file")

    loading.value = true
    try {
        const formData = new FormData()
        formData.append('file', file.value)

        const mapPayload: any = {
            date: mapping.value.date,
            description: mapping.value.description,
            reference: mapping.value.reference,
            balance: mapping.value.balance,
            credit_limit: mapping.value.credit_limit
        }

        if (mapping.value.mode === 'single') {
            mapPayload.amount = mapping.value.amount
        } else {
            mapPayload.debit = splitMapping.value.debit
            mapPayload.credit = splitMapping.value.credit
        }

        formData.append('mapping', JSON.stringify(mapPayload))
        formData.append('header_row_index', String(detectedHeaderRow.value))

        const res = await financeApi.parseCsv(formData) // Uses universal parser now
        parsedTxns.value = res.data
        selectedTxns.value = new Set(parsedTxns.value.map((_, i) => i))

        step.value = 4
    } catch (e: any) {
        notify.error(e.response?.data?.detail || "Failed to parse file")
    } finally {
        loading.value = false
    }
}

function removeTxn(index: number) {
    selectedTxns.value.delete(index)
}

function toggleSelection(index: number) {
    if (selectedTxns.value.has(index)) {
        selectedTxns.value.delete(index)
    } else {
        selectedTxns.value.add(index)
    }
}

async function importSelected() {
    loading.value = true
    try {
        const finalTxns = parsedTxns.value.filter((_, i) => selectedTxns.value.has(i))
        const source = file.value?.name.endsWith('.csv') ? 'CSV' : 'EXCEL'

        const res = await financeApi.importCsv({
            account_id: selectedAccount.value,
            transactions: finalTxns,
            source: source
        })

        // Save Mapping to Account
        const currentMapping = {
            mapping: {
                date: mapping.value.date,
                description: mapping.value.description,
                reference: mapping.value.reference,
                balance: mapping.value.balance,
                credit_limit: mapping.value.credit_limit,
                amount: mapping.value.amount,
                mode: mapping.value.mode
            },
            splitMapping: {
                debit: splitMapping.value.debit,
                credit: splitMapping.value.credit
            },
            mode: mapping.value.mode
        }

        try {
            await financeApi.updateAccount(selectedAccount.value, {
                import_config: JSON.stringify(currentMapping)
            })
        } catch (e) {
            console.error("Failed to save mapping preference", e)
        }

        importResult.value = res.data
        step.value = 5
        notify.success(`Imported ${res.data.imported} transactions`)
        emit('import-success')
    } catch (e: any) {
        notify.error("Import failed")
    } finally {
        loading.value = false
    }
}

function reset() {
    step.value = 1
    file.value = null
    parsedTxns.value = []
    importResult.value = null
    selectedAccount.value = ''
}

function close() {
    emit('close')
}
</script>

<template>
    <Teleport to="body">
        <div v-if="isOpen" class="modal-overlay-global">
            <div class="modal-global large-modal">
                <div class="modal-header">
                    <h2 class="modal-title">Import Transactions</h2>
                    <button class="btn-icon" @click="close">✕</button>
                </div>

                <!-- Stepper (Fixed) -->
                <div class="stepper">
                    <div class="step" :class="{ active: step >= 1 }"><span class="step-num">1</span> Upload</div>
                    <div class="line"></div>
                    <div class="step" :class="{ active: step >= 2 }"><span class="step-num">2</span> Preview</div>
                    <div class="line"></div>
                    <div class="step" :class="{ active: step >= 3 }"><span class="step-num">3</span> Map</div>
                    <div class="line"></div>
                    <div class="step" :class="{ active: step >= 4 }"><span class="step-num">4</span> Verify</div>
                </div>

                <!-- Content Body (Scrollable) -->
                <div v-if="loading" class="loading">Processing...</div>
                <div v-else class="content-body">
                    <div class="step-container">
                        <!-- Step 1: Upload -->
                        <div v-if="step === 1">
                            <div class="form-group">
                                <label>Account</label>
                                <CustomSelect v-model="selectedAccount" :options="accountOptions"
                                    placeholder="Select Bank Account" />
                            </div>
                            <div class="form-group">
                                <label>File (CSV / Excel)</label>
                                <input type="file" @change="handleFileUpload" accept=".csv, .xlsx, .xls"
                                    class="file-input" />
                            </div>
                        </div>

                        <!-- Step 2: Preview -->
                        <div v-if="step === 2">
                            <div v-if="analyzing" class="loading">Analyzing file structure...</div>

                            <div v-else>
                                <div class="mapping-instructions">
                                    <div class="instruction-card">
                                        <div class="icon">👀</div>
                                        <div>
                                            <h3>Review File Content</h3>
                                            <p>We found <strong>{{ csvHeaders.length }} columns</strong> starting at Row
                                                {{ detectedHeaderRow + 1 }}. Does this look right?</p>
                                        </div>
                                    </div>
                                </div>

                                <div v-if="previewRows.length > 0" class="preview-section">
                                    <h4>Files Preview (First 3 Rows)</h4>
                                    <div class="scroll-x">
                                        <table class="mini-table">
                                            <thead>
                                                <tr>
                                                    <th v-for="h in csvHeaders" :key="h">{{ h }}</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr v-for="(row, idx) in previewRows.slice(0, 3)" :key="idx">
                                                    <td v-for="h in csvHeaders" :key="h">{{ row[h] }}</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Step 3: Mapping -->
                        <div v-if="step === 3">
                            <div class="mapping-instructions">
                                <!-- Instructions removed to save space -->
                            </div>

                            <div class="mapping-container">
                                <!-- Core Fields Card -->
                                <div class="mapping-card">
                                    <div class="card-header">
                                        <h3>Transaction Details</h3>
                                    </div>
                                    <div class="card-body">
                                        <!-- Date -->
                                        <div class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">📅</span>
                                                <div class="text">
                                                    <span class="name">Date</span>
                                                    <span class="desc">Transaction date</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.date"
                                                    class="form-input" placeholder="Column Name" />
                                                <select v-else v-model="mapping.date" class="form-select">
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <!-- Description -->
                                        <div class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">📝</span>
                                                <div class="text">
                                                    <span class="name">Description</span>
                                                    <span class="desc">Payee or narration</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.description"
                                                    class="form-input" placeholder="Column Name" />
                                                <select v-else v-model="mapping.description" class="form-select">
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <!-- Reference -->
                                        <div class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">🆔</span>
                                                <div class="text">
                                                    <span class="name">Reference</span>
                                                    <span class="desc">Reference / UTR / Txn #</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.reference"
                                                    class="form-input" placeholder="Column Name (e.g. Ref No)" />
                                                <select v-else v-model="mapping.reference" class="form-select">
                                                    <option value="">-- No Reference --</option>
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <!-- Balance -->
                                        <div class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">💰</span>
                                                <div class="text">
                                                    <span class="name">Balance</span>
                                                    <span class="desc">Available balance after txn</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.balance"
                                                    class="form-input" placeholder="Column Name (e.g. Balance)" />
                                                <select v-else v-model="mapping.balance" class="form-select">
                                                    <option value="">-- No Balance --</option>
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <!-- Credit Limit -->
                                        <div class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">💳</span>
                                                <div class="text">
                                                    <span class="name">Credit Limit</span>
                                                    <span class="desc">New credit limit if updated</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.credit_limit"
                                                    class="form-input" placeholder="Column Name (e.g. Limit)" />
                                                <select v-else v-model="mapping.credit_limit" class="form-select">
                                                    <option value="">-- No Limit --</option>
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Financials Card -->
                                <div class="mapping-card">
                                    <div class="card-header">
                                        <h3>Financials</h3>
                                    </div>
                                    <div class="card-body">
                                        <!-- Amount Mode Toggle -->
                                        <div class="mode-toggle">
                                            <div class="toggle-option" :class="{ active: mapping.mode === 'single' }"
                                                @click="mapping.mode = 'single'">
                                                <span class="icon">💰</span> Single Column
                                            </div>
                                            <div class="toggle-option" :class="{ active: mapping.mode === 'split' }"
                                                @click="mapping.mode = 'split'">
                                                <span class="icon">⚖️</span> Split (Debit/Credit)
                                            </div>
                                        </div>

                                        <!-- Single Amount -->
                                        <div v-if="mapping.mode === 'single'" class="mapping-row">
                                            <div class="field-label">
                                                <span class="field-icon">💵</span>
                                                <div class="text">
                                                    <span class="name">Amount</span>
                                                    <span class="desc">Mixed +/- values</span>
                                                </div>
                                            </div>
                                            <div class="connector">→</div>
                                            <div class="field-input">
                                                <input v-if="csvHeaders.length === 0" v-model="mapping.amount"
                                                    class="form-input" placeholder="Column Name" />
                                                <select v-else v-model="mapping.amount" class="form-select">
                                                    <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <!-- Split Amount -->
                                        <template v-else>
                                            <div class="mapping-row">
                                                <div class="field-label">
                                                    <span class="field-icon">➖</span>
                                                    <div class="text">
                                                        <span class="name">Debit</span>
                                                        <span class="desc">Money out</span>
                                                    </div>
                                                </div>
                                                <div class="connector">→</div>
                                                <div class="field-input">
                                                    <input v-if="csvHeaders.length === 0" v-model="splitMapping.debit"
                                                        class="form-input" placeholder="Column Name" />
                                                    <select v-else v-model="splitMapping.debit" class="form-select">
                                                        <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}
                                                        </option>
                                                    </select>
                                                </div>
                                            </div>
                                            <div class="mapping-row">
                                                <div class="field-label">
                                                    <span class="field-icon">➕</span>
                                                    <div class="text">
                                                        <span class="name">Credit</span>
                                                        <span class="desc">Money in</span>
                                                    </div>
                                                </div>
                                                <div class="connector">→</div>
                                                <div class="field-input">
                                                    <input v-if="csvHeaders.length === 0" v-model="splitMapping.credit"
                                                        class="form-input" placeholder="Column Name" />
                                                    <select v-else v-model="splitMapping.credit" class="form-select">
                                                        <option v-for="h in csvHeaders" :key="h" :value="h">{{ h }}
                                                        </option>
                                                    </select>
                                                </div>
                                            </div>
                                        </template>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Step 4: Verification -->
                        <div v-if="step === 4">
                            <div class="verify-header">
                                <p>{{ selectedTxns.size }} rows selected</p>
                            </div>
                            <div class="table-container">
                                <table>
                                    <thead>
                                        <tr>
                                            <th><input type="checkbox" checked
                                                    @click="selectedTxns.size < parsedTxns.length ? selectedTxns = new Set(parsedTxns.map((_, i) => i)) : selectedTxns.clear()" />
                                            </th>
                                            <th>Date</th>
                                            <th>Ref #</th> <!-- Added Ref Column -->
                                            <th>Recipient / Source</th>
                                            <th>Description</th>
                                            <th>Amount</th>
                                            <th>Type</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="(txn, idx) in parsedTxns" :key="idx"
                                            :class="{ 'disabled': !selectedTxns.has(idx) }">
                                            <td><input type="checkbox" :checked="selectedTxns.has(idx)"
                                                    @change="toggleSelection(idx)" /></td>
                                            <td>{{ txn.date }}</td>
                                            <td><small>{{ txn.external_id || txn.ref_id || '-' }}</small></td>
                                            <!-- Display ID -->
                                            <td><strong>{{ txn.recipient || '-' }}</strong></td>
                                            <td>{{ txn.description }}</td>
                                            <td :class="txn.type">{{ formatAmount(txn.amount) }}</td>
                                            <td><span class="badge">{{ txn.type }}</span></td>
                                            <td><button class="btn-icon danger" @click="removeTxn(idx)">✕</button></td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Step 5: Done -->
                        <div v-if="step === 5" class="center-content">
                            <div class="success-icon">✅</div>
                            <h2>Import Complete!</h2>
                            <p>Successfully imported {{ importResult.imported }} transactions.</p>
                            <div v-if="importResult.errors.length > 0" class="errors">
                                <h3>Errors ({{ importResult.errors.length }})</h3>
                                <ul>
                                    <li v-for="err in importResult.errors" :key="err">{{ err }}</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Fixed Footer -->
                <div class="modal-footer">
                    <template v-if="step === 1">
                        <button class="btn btn-primary" @click="step = 2" :disabled="!selectedAccount || !file">Next:
                            Map Columns</button>
                    </template>
                    <template v-else-if="step === 2">
                        <button class="btn btn-outline" @click="step = 1">Back</button>
                        <button class="btn btn-primary" @click="step = 3">Yes, Looks Good</button>
                    </template>
                    <template v-else-if="step === 3">
                        <button class="btn btn-outline" @click="step = 2">Back</button>
                        <button class="btn btn-primary" @click="parseFile">Next: Verify</button>
                    </template>
                    <template v-else-if="step === 4">
                        <button class="btn btn-outline" @click="step = 3">Back</button>
                        <button class="btn btn-primary" @click="importSelected">Import Selected</button>
                    </template>
                    <template v-else-if="step === 5">
                        <button class="btn btn-primary" @click="close">Done</button>
                    </template>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
/* Reuse globals + some specific */
/* Reuse globals + some specific */
.large-modal {
    max-width: 1000px;
    width: 95%;
    height: auto;
    /* Allow auto height */
    max-height: 90vh;
    /* Cap at 90vh */
    display: flex;
    flex-direction: column;
    overflow: hidden;
    /* No outer scroll */
}

/* Modal Header & Footer are fixed by flex layout */
.modal-header {
    flex-shrink: 0;
    padding: 1rem;
    border-bottom: 1px solid var(--color-border);
}

.modal-footer {
    flex-shrink: 0;
    padding: 1rem;
    border-top: 1px solid var(--color-border);
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    background: var(--color-surface);
}

/* Scrollable Content Body */
.content-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    /* X handled by inner containers */
    padding: 1rem;
    padding-bottom: 1.5rem;
    /* Breathing room */
    min-height: 0;
    /* Flex fix */
}

/* Stepper also fixed at top */
.stepper {
    flex-shrink: 0;
    margin-bottom: 0;
    padding: 1rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-background);
}

.stepper {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--color-border);
    padding-bottom: 1rem;
}

.step {
    font-size: 0.9rem;
    color: var(--color-text-muted);
    opacity: 0.7;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.step-num {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--color-border);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
}

.step.active {
    opacity: 1;
    color: var(--color-primary);
    font-weight: 500;
}

.step.active .step-num {
    background: var(--color-primary);
}

.line {
    width: 40px;
    height: 2px;
    background: var(--color-border);
    border-radius: 2px;
}

.step-container {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

/* Unified vertical rhythm */

.form-group {
    margin-bottom: 0;
}

/* Remove bottom margin rely on gap */
.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.file-input {
    display: block;
    width: 100%;
    padding: 0.75rem;
    border: 1px dashed var(--color-border);
    border-radius: 6px;
    background: #f8fafc;
    transition: all 0.2s;
}

.file-input:hover {
    border-color: var(--color-primary);
    background: #f0f9ff;
}

/* Clean up ad-hoc margins */
.mapping-instructions {
    margin-bottom: 0;
}

.preview-section {
    margin-bottom: 0;
    background: var(--color-surface);
    padding: 1rem;
    border-radius: 8px;
    border: 1px solid var(--color-border);
}

.mapping-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.field.full {
    grid-column: span 2;
}

.form-input,
.form-select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-background);
    color: var(--color-text-main);
}

.table-container {
    border: 1px solid var(--color-border);
    border-radius: 4px;
    max-height: 400px;
    overflow-y: auto;
}

.table-container::-webkit-scrollbar {
    width: 8px;
    background: transparent;
}

.table-container::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 4px;
}

.table-container:hover::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}

th {
    position: sticky;
    top: 0;
    background: var(--color-surface);
    z-index: 1;
    text-align: left;
    padding: 0.5rem;
}

td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--color-border);
}

.DEBIT {
    color: var(--color-danger);
}

.CREDIT {
    color: var(--color-success);
}

.disabled {
    opacity: 0.5;
}

.center-content {
    text-align: center;
    padding: 2rem;
}

.success-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.errors {
    text-align: left;
    margin-top: 1rem;
    background: #fff0f0;
    padding: 1rem;
    border: 1px solid #ffcccc;
    color: #cc0000;
}

/* .modal-footer removed duplicate */
.hint {
    font-size: 0.9rem;
    color: var(--color-text-muted);
    margin-bottom: 1rem;
}

.mapping-instructions {
    margin-bottom: 2rem;
}

/* .instruction-card duplicate removed */

.preview-section h4 {
    margin-top: 0;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.scroll-x {
    overflow-x: auto;
    overflow-y: hidden;
    border: 1px solid var(--color-border);
    border-radius: 4px;
}

.scroll-x::-webkit-scrollbar {
    height: 8px;
    background: transparent;
}

.scroll-x::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 4px;
}

.scroll-x:hover::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
}

.mini-table {
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}

.mini-table th,
.mini-table td {
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    white-space: nowrap;
}

.mini-table th {
    background: var(--color-background);
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.75rem;
}

.mini-table tbody tr:nth-child(even) {
    background-color: #f8fafc;
}

.mini-table tbody tr:hover {
    background-color: #f1f5f9;
}

/* Enhanced Instruction Card */
.instruction-card {
    display: flex;
    gap: 1rem;
    background: #f0f9ff;
    /* Light Blue */
    border: 1px solid #bae6fd;
    padding: 1.25rem;
    border-radius: 8px;
    align-items: flex-start;
}

.instruction-card .icon {
    font-size: 1.5rem;
    background: #fff;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    box-shadow: var(--shadow-sm);
}

.instruction-card h3 {
    margin: 0 0 0.25rem 0;
    font-size: 1rem;
    color: #0284c7;
}

.instruction-card p {
    margin: 0;
    font-size: 0.9rem;
    color: #334155;
}


/* Redesigned Mapping */
/* Redesigned Mapping - Side-by-Side */
.mapping-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    align-items: start;
}

@media (max-width: 640px) {
    .mapping-container {
        grid-template-columns: 1fr;
    }
}

.mapping-card {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
    height: 100%;
}

.card-header {
    background: #f8fafc;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
}

.card-header h3 {
    margin: 0;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.card-body {
    padding: 0.75rem;
}

.mapping-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    gap: 0.75rem;
}

.mapping-row:last-child {
    margin-bottom: 0;
}

.field-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
}

.field-icon {
    width: 28px;
    height: 28px;
    background: #f1f5f9;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}

.field-label .text {
    display: flex;
    flex-direction: column;
}

.field-label .name {
    font-weight: 500;
    font-size: 0.9rem;
}

.field-label .desc {
    font-size: 0.75rem;
    color: var(--color-text-muted);
}

.connector {
    color: var(--color-text-muted);
    opacity: 0.5;
    font-size: 1rem;
}

.field-input {
    flex: 1;
    max-width: 50%;
}

.form-select,
.form-input {
    padding: 0.4rem 0.6rem;
    font-size: 0.9rem;
}

.mode-toggle {
    display: flex;
    background: #f1f5f9;
    padding: 0.2rem;
    border-radius: 6px;
    margin-bottom: 1rem;
}

.toggle-option {
    flex: 1;
    text-align: center;
    padding: 0.35rem;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--color-text-muted);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.toggle-option:hover {
    color: var(--color-text-main);
}

.toggle-option.active {
    background: white;
    color: var(--color-primary);
    box-shadow: var(--shadow-sm);
    font-weight: 600;
}

.badge-optional {
    font-size: 0.7rem;
    background: #f1f5f9;
    border: 1px solid var(--color-border);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    margin-left: 0.5rem;
    font-weight: normal;
    color: var(--color-text-muted);
}
</style>
