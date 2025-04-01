HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'
}

# Base URLs for each country
BASE_URLS = {
    "NZ": "https://www.health.govt.nz",
    "AU": "https://www.health.gov.au"
}

DATA_PROVIDER_URLS = {
    "NZ": [
        "https://www.health.govt.nz/regulation-legislation/certification-of-health-care-services/certified-providers/public-hospitals", 
        "https://www.health.govt.nz/regulation-legislation/certification-of-health-care-services/certified-providers/private-hospitals"
    ],
    "AU": [
        "https://www.health.gov.au/resources/publications/list-of-declared-hospitals?language=en"
    ]
}

# Email notification settings
EMAIL_CONFIG = {
    # Default SMTP settings (can be overridden in the UI)
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": 587,
    "USE_TLS": True,  # Use TLS encryption
    
    # Email content settings
    "EMAIL_SUBJECT_PREFIX": "[Hospital Data Fetcher] ",
    "EMAIL_FROM_NAME": "Hospital Data Fetcher",
    
    # Maximum number of recipients allowed in a single email
    "MAX_RECIPIENTS": 10,
    
    # Email templates
    "TEMPLATES": {
        "NEW_FILES": """
New hospital data files have been downloaded.

{message}

Files Downloaded:
{files_list}

Timestamp: {timestamp}

--
This is an automated notification from the Hospital Data Fetcher application.
        """,
        "ERROR": """
An error occurred while fetching hospital data.

Error details:
{error_message}

Timestamp: {timestamp}

--
This is an automated notification from the Hospital Data Fetcher application.
        """
    }
}