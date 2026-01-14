import axios, { type AxiosInstance } from 'axios'

// Create Axios instance
const apiClient: AxiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_DIR || '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor for API calls
apiClient.interceptors.request.use(
    async (config) => {
        const token = localStorage.getItem('access_token')
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Response interceptor for API calls
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        // Handle 401 Unauthorized (e.g., token expired)
        if (error.response && error.response.status === 401) {
            // Clear token and redirect to login if not already there
            localStorage.removeItem('access_token')
            // router.push('/login') // Would require importing router/store 
        }
        return Promise.reject(error)
    }
)

export default apiClient

export interface AccountCreate {
    name: string;
    type: string;
    currency: string;
    account_mask?: string;
    balance?: number;
    owner_name?: string;
}

export interface AccountUpdate {
    name?: string;
    type?: string;
    currency?: string;
    account_mask?: string;
    owner_name?: string;
}

export interface TransactionUpdate {
    category?: string;
    description?: string;
}

export const financeApi = {
    getAccounts: () => apiClient.get('/finance/accounts'),
    createAccount: (data: AccountCreate) => apiClient.post('/finance/accounts', data),
    updateAccount: (id: string, data: AccountUpdate) => apiClient.put(`/finance/accounts/${id}`, data),
    deleteAccount: (id: string) => apiClient.delete(`/finance/accounts/${id}`),
    getAccountTransactionCount: (id: string) => apiClient.get(`/finance/accounts/${id}/transaction-count`),
    getTransactions: (accountId?: string, page: number = 1, limit: number = 50, startDate?: string, endDate?: string) =>
        apiClient.get('/finance/transactions', { params: { account_id: accountId, page, limit, start_date: startDate, end_date: endDate } }),
    updateTransaction: (id: string, data: TransactionUpdate) => apiClient.put(`/finance/transactions/${id}`, data),
    smartCategorize: (data: { transaction_id: string, category: string, create_rule: boolean, apply_to_similar: boolean }) =>
        apiClient.post('/finance/transactions/smart-categorize', data),
    bulkDeleteTransactions: (ids: string[]) => apiClient.post('/finance/transactions/bulk-delete', { transaction_ids: ids }),
    getMetrics: () => apiClient.get('/finance/metrics'),
    getRules: () => apiClient.get('/finance/rules'),
    getRuleSuggestions: () => apiClient.get('/finance/rules/suggestions'),
    createRule: (data: any) => apiClient.post('/finance/rules', data),
    updateRule: (id: string, data: any) => apiClient.put(`/finance/rules/${id}`, data),
    deleteRule: (id: string) => apiClient.delete(`/finance/rules/${id}`),

    getCategories: () => apiClient.get('/finance/categories'),
    createCategory: (data: any) => apiClient.post('/finance/categories', data),
    updateCategory: (id: string, data: any) => apiClient.put(`/finance/categories/${id}`, data),
    deleteCategory: (id: string) => apiClient.delete(`/finance/categories/${id}`),

    getBudgets: () => apiClient.get('/finance/budgets'),
    setBudget: (data: any) => apiClient.post('/finance/budgets', data),
    deleteBudget: (id: string) => apiClient.delete(`/finance/budgets/${id}`),

    // Ingestion
    analyzeCsv: (formData: FormData) => apiClient.post('/ingestion/csv/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    parseCsv: (formData: FormData) => apiClient.post('/ingestion/csv/parse', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    importCsv: (data: any) => apiClient.post('/ingestion/csv/import', data),

    // Email Automations
    getEmailConfigs: () => apiClient.get('/ingestion/email/configs'),
    createEmailConfig: (data: any) => apiClient.post('/ingestion/email/configs', data),
    deleteEmailConfig: (id: string) => apiClient.delete(`/ingestion/email/configs/${id}`),
    updateEmailConfig: (id: string, data: any) => apiClient.put(`/ingestion/email/configs/${id}`, data),
    getEmailSyncLogs: (id: string) => apiClient.get(`/ingestion/email/configs/${id}/logs`),
    syncEmailConfig: (id: string) => apiClient.post(`/ingestion/email/sync/${id}`),

    // Tenants / Management
    getTenants: () => apiClient.get('/auth/tenants'),
    updateTenant: (id: string, data: any) => apiClient.put(`/auth/tenants/${id}`, data),

    // Triage & Training
    getTriage: () => apiClient.get('/ingestion/triage'),
    approveTriage: (id: string, category?: string) => apiClient.post(`/ingestion/triage/${id}/approve`, { category }),
    rejectTriage: (id: string) => apiClient.delete(`/ingestion/triage/${id}`),
    getTraining: () => apiClient.get('/ingestion/training'),
    labelMessage: (id: string, data: any) => apiClient.post(`/ingestion/training/${id}/label`, data),
    dismissTrainingMessage: (id: string) => apiClient.delete(`/ingestion/training/${id}`),

    // User Management
    getMe: () => apiClient.get<any>('/auth/me'),
    getUsers: () => apiClient.get<any[]>('/auth/users'),
    createUser: (data: any) => apiClient.post('/auth/users', data),
    updateUser: (id: string, data: any) => apiClient.put(`/auth/users/${id}`, data),
}

export const aiApi = {
    getSettings: () => apiClient.get('/ingestion/ai/settings'),
    updateSettings: (data: any) => apiClient.post('/ingestion/ai/settings', data),
    testConnection: (content: string) => apiClient.post('/ingestion/ai/test', { content }),
    listModels: (provider: string, apiKey?: string) => apiClient.get('/ingestion/ai/models', { params: { provider, api_key: apiKey } })
}
