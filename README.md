# 📦 InventoTrack

Welcome! I'm thrilled to share **InventoTrack**, an end-to-end Inventory & Finance Management web application built as a showcase of my full-stack development capabilities. 

## 👋 Hello, Recruiters & Hiring Managers!
If you're reading this, thank you for taking the time to review my portfolio! I built this project to demonstrate my ability to develop a production-ready, full-stack web application from scratch. This project highlights my proficiency in:
- Building robust Python RESTful APIs.
- Integrating modern frontend reactivity without relying on heavy frameworks.
- Designing and querying NoSQL databases.
- Containerizing applications for reliable deployment.

I would love to discuss how the technical decisions and skills demonstrated here can bring value to your engineering team. Feel free to explore the codebase and try out the app!

## 🚀 About The Project
InventoTrack is a comprehensive dashboard application designed to help businesses seamlessly track their inventory stock, monitor financial transactions, and manage delivery logistics. The application acts as a single source of truth for both warehouse and financial operations, ensuring that stock levels and financial ledgers are always perfectly synchronized.

### ✨ Key Features
- **📊 Real-time Dashboard:** A dynamic analytics dashboard utilizing Chart.js to visualize revenue, expenses, and transaction trends over time.
- **📦 Inventory Management:** Complete CRUD operations for items, including stock tracking, purchase/selling price management, and low-stock alerts.
- **💰 Financial Tracking:** Automatically calculate profit margins, incoming revenue, and outgoing expenses based on inventory movements.
- **🚚 Delivery & Logistics:** A dedicated module for tracking outgoing shipments, updating delivery statuses, tracking history, and managing estimated arrival times.
- **🔒 Secure Authentication:** Role-based access control secured by stateless JWT (JSON Web Tokens).
- **⚡ Reactive UI:** Built with Alpine.js to provide a smooth, Single-Page-Application (SPA) feel while keeping the bundle size minimal.

## 🛠️ Technology Stack
- **Backend:** Python 3.12, Flask, Pydantic (Strict Data Validation)
- **Frontend:** HTML5, Tailwind CSS (Styling), Alpine.js (Reactivity), Chart.js (Data Visualization)
- **Database:** MongoDB
- **Deployment:** Docker, Gunicorn (WSGI Server)

## ⚙️ How It Works
The architecture follows a decoupled approach where the Flask backend serves purely as a JSON API, and the frontend templates consume this data asynchronously. 
- **Data Flow:** When an item is added or a transaction is made, the backend calculates the financial implications using complex queries and aggregations.
- **Validation:** All incoming requests are strictly validated using Pydantic schemas to ensure data integrity before touching the database.
- **UI Reactivity:** Alpine.js binds the fetched API data directly to the DOM, handling state management (like loading spinners, modals, and dynamic charts) entirely within the HTML templates.

## 🏃‍♂️ Getting Started (Local Setup)

### Prerequisites
- Docker and Docker Compose installed on your machine.
- A MongoDB instance (Local or MongoDB Atlas URI).

### Installation
1. **Clone this repository:**
```bash
git clone https://github.com/yourusername/inventory-finance-tracker.git
cd inventory-finance-tracker
```

2. **Configure Environment Variables:**
Create a `.env` file in the root directory:
```env
MONGO_URI=mongodb://host.docker.internal:27017/inventory_db
JWT_SECRET_KEY=your_super_secret_jwt_key
FLASK_ENV=production
```

3. **Build and Run via Docker:**
```bash
docker build -t inventory-app .
docker run -d -p 5000:5000 --env-file .env inventory-app
```

4. **Access the Application:**
Open your browser and navigate to: `http://localhost:5000`

---
*Thank you again for visiting my portfolio. Let's build something great together!*
