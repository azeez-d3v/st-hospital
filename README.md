# Hospital Data Fetcher

A Streamlit application for automatically fetching, monitoring, and analyzing hospital data from government health websites in New Zealand and Australia.

## 📋 Overview

The Hospital Data Fetcher is designed to regularly check health department websites, download the latest hospital data files (CSV/Excel), and provide analytics on the data availability and changes over time. The application helps healthcare organizations and researchers maintain up-to-date information on hospital facilities.

## ✨ Features

- **Automated Data Fetching**: Schedule automatic data fetching using various scheduling options (hourly, daily, weekly, monthly, or custom intervals)
- **Multiple Data Sources**: Supports data from multiple sources with toggles to enable/disable specific sources
- **Data Change Detection**: Only downloads files when they've changed from the previous version
- **Email Notifications**: Configure email alerts to receive notifications when new data is available
- **Analytics Dashboard**: Visualize fetch success rates and activity history
- **Data Visualization**: View and analyze fetched hospital data with built-in statistics and charts
- **Persistent Configuration**: All settings are saved locally and loaded automatically when the app starts

## 🔧 Installation

### Prerequisites

- Python 3.7+
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hospital-data-fetcher.git
cd hospital-data-fetcher
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## 🚀 Usage

1. Start the application:
```bash
streamlit run src/app.py
```

2. Access the web interface at http://localhost:8501

3. Configure data sources, schedules, and email notifications as needed

4. Click "Fetch Now" to manually fetch data or enable scheduling for automatic fetching

## 📊 Data Sources

The application currently fetches data from:

- **New Zealand Ministry of Health**
  - Public Hospitals
  - Private Hospitals
  
- **Australian Department of Health**
  - Declared Hospitals

Additional data sources can be added by modifying the `DATA_PROVIDER_URLS` dictionary in `src/config/settings.py`.

## ⏱️ Scheduling Options

- **Hourly**: Run at a specific minute of each hour
- **Daily**: Run at a specific time each day
- **Weekly**: Run on a specific day of the week at a specific time
- **Monthly**: Run on a specific day of the month at a specific time
- **Custom**: Run at a custom interval specified in minutes

## 📧 Email Notifications

Configure email notifications to receive alerts when new data is available:

1. Enable email notifications in the "Email Notifications" section
2. Configure SMTP server settings (server, port, TLS)
3. Enter sender email and password (For Gmail, use an App Password)
4. Add recipient email addresses
5. Test the configuration using the "Test Email Configuration" button

## 📁 File Storage

- Downloaded files are stored in `src/data/downloads/`
- Fetch logs are stored in `src/data/logs/`
- Configuration files are stored in `src/data/config/`

## 🔒 Security Notes

- Email passwords are stored in plain text in configuration files. Consider implementing a more secure method if needed.
- The application uses basic authentication for SMTP. For Gmail, generate an App Password rather than using your account password.

## 📝 Configuration

Application settings are saved in JSON format in the following files:

- `src/data/config/schedule_config.json`: Scheduling configuration
- `src/data/config/email_config.json`: Email notification settings
- `src/data/config/email_recipients.json`: Email recipient list

## 🧰 Troubleshooting

- If the application fails to fetch data, check the logs in `src/scheduler.log` and `src/data/logs/fetcher.log`
- Ensure the target websites are accessible and that the data file links follow the expected patterns
- For SMTP errors, verify your email server settings and credentials

## 📄 License

[MIT License](LICENSE)

## 🙏 Acknowledgements

- Built with [Streamlit](https://streamlit.io/)
- Uses data from [New Zealand Ministry of Health](https://www.health.govt.nz/) and [Australian Department of Health](https://www.health.gov.au/) 