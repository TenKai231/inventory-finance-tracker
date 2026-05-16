# 📊 Inventory & Finance Tracker

> **Built with passion for efficient business management.**  
> A modern web application designed to streamline inventory tracking and financial reporting for businesses and individuals.

---

## 👋 Welcome, HR Professionals & Visitors!

Thank you for visiting my portfolio project! This application represents my dedication to building practical, user-friendly solutions that solve real-world business challenges. Whether you're evaluating my technical skills or considering me for a role, I hope this project demonstrates my commitment to clean code, thoughtful design, and creating value through technology.

**🎯 Why This Project Matters:**  
In today's fast-paced business environment, managing inventory and finances manually is inefficient and error-prone. This system automates those processes, providing clear insights into stock levels, income, expenses, and profitability—all in one intuitive dashboard.

Feel free to explore the code, test the features, or reach out if you'd like to discuss how I can bring similar value to your team!

---

## 🌟 What This Web Application Does

**Inventory & Finance Tracker** is a comprehensive web-based system that helps businesses and individuals:

- **Track Inventory**: Monitor stock levels, add/update/remove items, and categorize products effortlessly.
- **Manage Finances**: Record income and expenses linked to inventory transactions.
- **Gain Insights**: Visualize profit/loss trends, top-selling items, and financial health through interactive charts.
- **Export Reports**: Generate Excel/CSV reports for deeper analysis or sharing with stakeholders.
- **Secure Access**: Role-based authentication ensures data privacy and security.

### 💡 How It Works (Simple Flow)

1. **Login/Register**: Users create an account and log in securely.
2. **Dashboard Overview**: Get instant insights via charts showing sales trends, inventory status, and financial summaries.
3. **Inventory Management**: Add products, update quantities, set prices, and organize by categories.
4. **Transaction Recording**: Log sales (income) or purchases (expenses), automatically updating inventory and financial records.
5. **Reporting**: Export data to Excel/CSV for external analysis or presentations.
6. **Real-time Updates**: Changes reflect immediately across the dashboard thanks to dynamic frontend-backend integration.

---

## 🚀 Tech Stack

This project leverages modern, industry-standard technologies:

**Backend:**
- **[Flask (Python)](https://flask.palletsprojects.com/)**: Lightweight yet powerful web framework for API development and server-side rendering.
- **[MongoDB](https://www.mongodb.com/)**: Flexible NoSQL database for scalable data storage.
- **Flask-JWT-Extended**: Secure token-based authentication.
- **Pandas & Openpyxl**: Advanced data processing for Excel/CSV exports and imports.

**Frontend:**
- **[Tailwind CSS](https://tailwindcss.com/)**: Utility-first CSS framework for rapid, responsive UI design.
- **[Alpine.js](https://alpinejs.dev/)**: Minimalist JavaScript for reactive DOM interactions without the overhead of heavy frameworks.
- **[Chart.js](https://www.chartjs.org/)**: Beautiful, interactive charts for data visualization.

---

## 🏗️ Project Structure (For Contributors & Reviewers)

Here's a clear map of the codebase to help you navigate:

```
inventory-finance-tracker/
├── app/                      # Core Backend Logic (Python/Flask)
│   ├── models/               # Database schemas and MongoDB queries
│   ├── routes/               # API endpoints and URL routing
│   │   ├── auth.py           # Login, Register, Authentication
│   │   ├── data.py           # CRUD operations for inventory & transactions
│   │   └── ui.py             # HTML page rendering (Jinja2 templates)
│   ├── services/             # Business logic helpers
│   ├── config.py             # App configuration settings
│   └── extensions.py         # Database connections and Flask extensions
├── static/                   # Public assets
│   ├── css/                  # Compiled Tailwind CSS
│   └── js/                   # Client-side scripts (e.g., dashboard charts)
├── templates/                # HTML templates (Jinja2)
├── tests/                    # Unit and integration tests
├── Dockerfile                # Docker containerization setup
├── package.json              # Node.js dependencies (Tailwind build)
├── requirements.txt          # Python dependencies
└── run.py                    # Main entry point to start the Flask server
```

---

## 🛠️ How to Run Locally

Get the project up and running on your machine in minutes:

### Prerequisites
- **Python 3.9+**
- **Node.js & npm** (for Tailwind CSS compilation)
- **MongoDB** (local instance or MongoDB Atlas cloud database)

### Step 1: Frontend Setup (Tailwind CSS)
```bash
npm install
npm run build
# Tip: Use `npm run dev` during development for auto-rebuild on changes
```

### Step 2: Backend Setup (Flask)
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (.env file)
# Create a .env file in the root directory with:
MONGO_URI="your_mongodb_connection_string"
SECRET_KEY="your_flask_secret_key"
JWT_SECRET_KEY="your_jwt_secret_key"

# Run the application
python run.py
```

Access the app at `http://127.0.0.1:5000` 🎉

---

## 🤝 Contributing

I welcome contributions! Here's how you can help:

1. **Understand the Codebase**: Refer to the **Project Structure** section above.
2. **Frontend Changes**: Edit files in `templates/` (HTML) and `static/` (CSS/JS).
3. **Backend/API Changes**: Modify `app/routes/` for new endpoints or logic.
4. **Database Logic**: Update `app/models/` for schema or query improvements.
5. **Git Workflow**:
   - Fork the repository.
   - Create a feature branch (`git checkout -b feature/your-feature-name`).
   - Commit your changes (`git commit -m "Add your feature description"`).
   - Push and open a Pull Request.

---

## 📬 Let's Connect!

If you're an HR professional, recruiter, or fellow developer who sees potential in this project—or if you'd like to collaborate—I'd love to hear from you!

- **Portfolio**: Explore more of my work [insert your portfolio link here].
- **LinkedIn**: [Your LinkedIn Profile]
- **Email**: [your.email@example.com]
- **GitHub**: Feel free to open an issue or discussion on this repo.

**Thank you for taking the time to explore my work!** 🙏  
This project is not just code—it's a reflection of my problem-solving mindset, attention to detail, and passion for creating tools that make a difference.

---

*Built with ❤️ by [Your Name]*  
*Last Updated: December 2025*
