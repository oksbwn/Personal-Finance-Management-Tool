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
    getTransactions: (accountId?: string) => apiClient.get('/finance/transactions', { params: { account_id: accountId } }),
    updateTransaction: (id: string, data: TransactionUpdate) => apiClient.put(`/finance/transactions/${id}`, data),
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
}
