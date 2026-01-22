# WealthFam

> [!IMPORTANT]
> **WealthFam** (formerly Finnera) is a premium, AI-driven personal and family finance management platform designed for the modern household.

![WealthFam Branding](/frontend/public/wordmark.png)

## 🚀 Overview

WealthFam provides a holistic view of your financial health. From daily expense tracking to complex investment management and AI-powered intelligence, WealthFam is built to help families refine their finances and achieve long-term growth.

## ✨ Key Features

### 🏦 Holistic Dashboard
- **Real-time Balance Sheet**: Instantly view your Net Worth, Liquidity, and Debt.
- **Spending Velocity**: Track your monthly spend with live sparklines and category-wise breakdowns.
- **Budget Pulse**: Monitor your budget health across different categories at a glance.

### 📈 Advanced Mutual Funds Tracking
- **Unified Portfolio**: Manage multiple folios and family members in one place.
- **XIRR & Performance**: Automated performance tracking with XIRR calculations and historical growth timelines.
- **Market Intelligence**: Live monitoring of major indices (NIFTY 50, SENSEX) and AMC-specific insights.
- **CAS Import**: Seamlessly ingest data from CAMS/KFintech via PDF upload or automated email scanning.

### 🤖 AI Financial Intelligence
- **Deep Insights**: Generate personalized spending vectors and optimization strategies using AI.
- **Predictive Analytics**: Forecast your future balance based on historical velocity and upcoming subscriptions.
- **Smart Categorization**: Automated classification of transactions for effortless organization.

### 💳 Credit Intelligence
- **Utilization Tracking**: Keep an eye on your credit card limits and utilization ratios.
- **Billing Cycles**: Stay ahead with notifications for upcoming bills and due dates.
- **Spending Patterns**: Specialized analytics for weekend vs. weekday spending and top merchant analysis.

### 🗓️ Subscription Management
- **Recurring Transactions**: Track all your active subscriptions and recurring bills.
- **Forecast Integration**: Subscriptions are automatically factored into your liquidity projections.

## 🛠️ Tech Stack

### Frontend
- **Framework**: [Vue.js 3](https://vuejs.org/) (Composition API)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Charts**: [Chart.js](https://www.chartjs.org/)
- **State Management**: Pinia

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Database**: [DuckDB](https://duckdb.org/) (Serverless SQL)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/)

## 🏁 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/wealthfam.git
   cd wealthfam
   ```

2. **Setup Backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. **Setup Frontend**:
   ```bash
   cd ../frontend
   npm install
   npm run dev
   ```

## 🔐 Security & Privacy
WealthFam is designed with data privacy at its core. By leveraging DuckDB, your financial data remains in a local, high-performance database, ensuring you have full control over your intelligence.

---
*WealthFam: Refine Your Finances*
