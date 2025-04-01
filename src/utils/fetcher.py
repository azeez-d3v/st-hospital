from curl_cffi import AsyncSession, exceptions
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Tuple
import json
import logging
import asyncio
from config.settings import BASE_URLS
from urllib.parse import urljoin, urlparse
import io

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler(os.path.join('src', 'data', 'logs', 'fetcher.log'))  # Output to file
    ]
)
logger = logging.getLogger(__name__)

class LinkFetcher:
    def __init__(self, headers: Dict, urls: Dict[str, List[str]], download_dir: str):
        self.headers = headers
        self.urls = urls
        self.download_dir = download_dir
        self.logs = []
        self.log_file = os.path.join(os.path.dirname(download_dir), 'logs', 'fetch_history.json')
        
        # Create directories if they don't exist
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Load existing logs
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                self.logs = json.load(f)
        logger.info(f"LinkFetcher initialized with download directory: {download_dir}")
    
    def _get_file_name(self, url, country):
        """Generate a standardized file name based on URL and country."""
        if country == "NZ":
            if "public-hospitals" in url:
                return "NZ_Public_Hospitals"
            elif "private-hospitals" in url:
                return "NZ_Private_Hospitals"
        elif country == "AU":
            if "declared-hospitals" in url:
                return "AU_Declared_Hospitals"
        
        # Fallback: Use URL parts
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        relevant_part = next((part for part in path_parts if 'hospital' in part), path_parts[-1])
        return f"{country}_{relevant_part.replace('-', '_').title()}"

    def _compare_data(self, new_df, existing_file):
        """Compare new data with existing data."""
        if not os.path.exists(existing_file):
            logger.info(f"No existing file found at {existing_file}, will save new data.")
            return False  # No existing file, save new data
            
        try:
            # Load existing data
            existing_df = pd.read_csv(existing_file)
            
            # Debug info
            logger.debug(f"Existing data shape: {existing_df.shape}, New data shape: {new_df.shape}")
            
            # Basic size check
            if len(existing_df) != len(new_df):
                logger.info(f"Row count mismatch: Existing {len(existing_df)}, New {len(new_df)}")
                return False
                
            # Make copies to avoid modifying originals
            existing_df_copy = existing_df.copy()
            new_df_copy = new_df.copy()
            
            # Reset indexes
            existing_df_copy.reset_index(drop=True, inplace=True)
            new_df_copy.reset_index(drop=True, inplace=True)
            
            # Make sure we can compare apples to apples
            if existing_df_copy.shape[1] != new_df_copy.shape[1]:
                logger.info(f"Column count mismatch: Existing {existing_df_copy.shape[1]}, New {new_df_copy.shape[1]}")
                return False
                
            # Process all columns in both dataframes to make them comparable
            for i, df in enumerate([existing_df_copy, new_df_copy]):
                df_name = "Existing" if i == 0 else "New"
                # Convert all columns to string to handle type differences
                for col in df.columns:
                    # Handle different data types appropriately
                    if pd.api.types.is_numeric_dtype(df[col]):
                        # For numeric, format to fixed precision to avoid float comparison issues
                        logger.debug(f"Converting numeric column {col} in {df_name} df")
                        df[col] = df[col].apply(lambda x: f"{float(x):.5f}" if pd.notnull(x) else "")
                    elif pd.api.types.is_datetime64_any_dtype(df[col]):
                        # For dates, convert to ISO format string
                        logger.debug(f"Converting datetime column {col} in {df_name} df")
                        df[col] = df[col].astype(str).str.replace('NaT', '')
                    else:
                        # For strings and other types, convert to string and strip whitespace
                        logger.debug(f"Converting column {col} in {df_name} df to string")
                        df[col] = df[col].astype(str).str.strip().str.replace('nan', '')
            
            # Simple check - if the processed dataframes have identical row counts and values
            # we consider them the same regardless of column names
            
            # Extract values as lists (easier to debug than numpy arrays)
            existing_values = existing_df_copy.values.tolist()
            new_values = new_df_copy.values.tolist()
            
            # Check for equality
            is_equal = True
            for i, (existing_row, new_row) in enumerate(zip(existing_values, new_values)):
                if existing_row != new_row:
                    is_equal = False
                    logger.debug(f"Difference in row {i}:")
                    logger.debug(f"  Existing: {existing_row}")
                    logger.debug(f"  New:      {new_row}")
                    # Only show a few differences to avoid log spam
                    if i >= 2:
                        logger.debug("More differences exist but not showing all...")
                        break
            
            logger.info(f"Final comparison result: {'EQUAL' if is_equal else 'DIFFERENT'}")
            return is_equal
            
        except Exception as e:
            logger.warning(f"Error comparing data: {str(e)}")
            import traceback
            logger.warning(traceback.format_exc())
            return False

    def _save_file(self, df, file_name):
        """Save DataFrame to file with comparison."""
        file_path = os.path.join(self.download_dir, f"{file_name}.csv")
        
        # Compare with existing data
        is_same = self._compare_data(df, file_path)
        if is_same:
            logger.info(f"Data unchanged for {file_name} - skipping save")
            return False
        
        # Save new data
        df.to_csv(file_path, index=False)
        logger.info(f"Saved new data to {file_name}")
        return True

    async def fetch_links(self):
        """Fetch links from all configured URLs."""
        results = {}
        total_attempts = 0
        successful = 0
        failed = 0

        async with AsyncSession() as session:
            for country, urls in self.urls.items():
                results[country] = []
                for url in urls:
                    try:
                        response = await session.get(url, headers=self.headers, impersonate="chrome131")
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            # Find all links that might be CSV or Excel files
                            links = []
                            for link in soup.find_all('a'):
                                href = link.get('href', '')
                                if any(ext in href.lower() for ext in ['.csv', '.xlsx', '.xls']):
                                    full_url = urljoin(url, href)
                                    links.append({
                                        'url': full_url,
                                        'base_url': url,
                                        'text': link.get_text(strip=True)
                                    })
                            
                            results[country].extend(links)
                            successful += len(links)
                        else:
                            failed += 1
                            logging.error(f"Failed to fetch {url}: Status {response.status_code}")
                    except Exception as e:
                        failed += 1
                        logging.error(f"Error fetching {url}: {str(e)}")
                    
                    total_attempts += 1

        # Log the fetch operation
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'total_attempts': total_attempts,
            'successful': successful,
            'failed': failed
        }
        self.logs.append(log_entry)
        
        # Save logs
        with open(self.log_file, 'w') as f:
            json.dump(self.logs, f)

        return results, log_entry

    async def download_files(self, results):
        """Download files from the fetched links."""
        downloaded = {}
        
        async with AsyncSession() as session:
            for country, links in results.items():
                downloaded[country] = []
                for link in links:
                    try:
                        response = await session.get(link['url'], headers=self.headers, impersonate="chrome131")
                        if response.status_code == 200:
                            content = response.content
                            
                            # Convert to DataFrame based on file type
                            try:
                                if link['url'].endswith('.csv'):
                                    df = pd.read_csv(io.BytesIO(content))
                                else:  # Excel
                                    df = pd.read_excel(io.BytesIO(content))
                                
                                # Generate file name
                                file_name = self._get_file_name(link['base_url'], country)
                                
                                # Save file with comparison
                                if self._save_file(df, file_name):
                                    downloaded[country].append(file_name)
                                    
                            except Exception as e:
                                logging.error(f"Error processing file from {link['url']}: {str(e)}")
                        else:
                            logging.error(f"Failed to download {link['url']}: Status {response.status_code}")
                    except Exception as e:
                        logging.error(f"Error downloading {link['url']}: {str(e)}")

        return downloaded

    def _save_logs(self):
        """Save logs to file."""
        with open(self.log_file, 'w') as f:
            json.dump(self.logs, f, indent=4)
            logger.debug("Fetch history saved to file") 