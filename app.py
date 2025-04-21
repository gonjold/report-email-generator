import streamlit as st
import os
import json
import configparser
from datetime import datetime
import io
import base64
import time
from pathlib import Path

# Import processing functions
from pptx_extractor import extract_text_from_pptx
from kpi_extractor import extract_kpis_with_ai
from email_generator import generate_email, are_pmax_and_vla_identical

# Set page config
st.set_page_config(page_title="Dealership Report Parser", layout="wide")

# --- Styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 600;
        color: #1E88E5;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 500;
        color: #0D47A1;
    }
    .info-text {
        font-size: 1rem;
        color: #424242;
    }
    .highlight {
        background-color: #E3F2FD;
        padding: 0.5rem;
        border-radius: 0.3rem;
    }
    .success-text {
        color: #4CAF50;
        font-weight: bold;
    }
    .warning-text {
        color: #FF9800;
        font-weight: bold;
    }
    .error-text {
        color: #F44336;
        font-weight: bold;
    }
    .stButton>button {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
    }
    .report-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 20px;
        background-color: #FAFAFA;
    }
    .report-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .metric-header {
        font-weight: bold;
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration Management ---
CONFIG_FILE = "parser_config.ini"

def load_config():
    """Load API keys from config file or environment variables"""
    config = {
        "claude_api_key": None,
        "openai_api_key": None,
        "deepseek_api_key": None,
        "default_ai": "claude"
    }
    
    # Try to load from Streamlit secrets
    try:
        if "API_KEYS" in st.secrets:
            config["claude_api_key"] = st.secrets["API_KEYS"].get("claude")
            config["openai_api_key"] = st.secrets["API_KEYS"].get("openai")
            config["deepseek_api_key"] = st.secrets["API_KEYS"].get("deepseek")
            config["default_ai"] = st.secrets.get("SETTINGS", {}).get("default_ai", config["default_ai"])
    except Exception as e:
        print(f"Error loading secrets: {e}")
    
    # Then try environment variables (as fallback)
    if not config["claude_api_key"]:
        config["claude_api_key"] = os.environ.get("CLAUDE_API_KEY")
    if not config["openai_api_key"]:
        config["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
    if not config["deepseek_api_key"]:
        config["deepseek_api_key"] = os.environ.get("DEEPSEEK_API_KEY")
    if not config["default_ai"]:
        config["default_ai"] = os.environ.get("DEFAULT_AI", config["default_ai"])
    
    # Then try config file
    if os.path.exists(CONFIG_FILE):
        parser = configparser.ConfigParser()
        parser.read(CONFIG_FILE)
        if "API_KEYS" in parser:
            if not config["claude_api_key"] and "claude" in parser["API_KEYS"]:
                config["claude_api_key"] = parser["API_KEYS"]["claude"]
            if not config["openai_api_key"] and "openai" in parser["API_KEYS"]:
                config["openai_api_key"] = parser["API_KEYS"]["openai"]
            if not config["deepseek_api_key"] and "deepseek" in parser["API_KEYS"]:
                config["deepseek_api_key"] = parser["API_KEYS"]["deepseek"]
        if "SETTINGS" in parser and "default_ai" in parser["SETTINGS"]:
            config["default_ai"] = parser["SETTINGS"]["default_ai"]
    
    return config

def save_config(config):
    """Save API keys to config file"""
    parser = configparser.ConfigParser()
    
    parser["API_KEYS"] = {
        "claude": config["claude_api_key"] or "",
        "openai": config["openai_api_key"] or "",
        "deepseek": config["deepseek_api_key"] or ""
    }
    
    parser["SETTINGS"] = {
        "default_ai": config["default_ai"]
    }
    
    with open(CONFIG_FILE, 'w') as f:
        parser.write(f)

def get_download_link(text, filename, link_text, is_html=False):
    """Generate a download link for text content"""
    if is_html:
        # Set MIME type for HTML content
        mime_type = "text/html"
    else:
        mime_type = "file/txt"
    
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def main():
    # Load configuration
    config = load_config()
    
    # Sidebar for configuration
    with st.sidebar:
        st.title("Configuration")
        
        # API Key Management
        st.header("API Keys")
        
        with st.expander("Manage API Keys"):
            claude_key = st.text_input("Claude API Key", value=config["claude_api_key"] or "", type="password")
            openai_key = st.text_input("OpenAI API Key", value=config["openai_api_key"] or "", type="password")
            deepseek_key = st.text_input("DeepSeek API Key", value=config["deepseek_api_key"] or "", type="password")
            
            if st.button("Save API Keys"):
                config["claude_api_key"] = claude_key
                config["openai_api_key"] = openai_key
                config["deepseek_api_key"] = deepseek_key
                save_config(config)
                st.success("API keys saved successfully!")
        
        # AI Provider Selection
        st.header("AI Provider")
        ai_options = []
        if config["claude_api_key"]:
            ai_options.append("claude")
        if config["openai_api_key"]:
            ai_options.append("openai")
        if config["deepseek_api_key"]:
            ai_options.append("deepseek")
        
        if not ai_options:
            st.warning("Please add at least one API key to continue.")
            selected_ai = None
        else:
            default_index = ai_options.index(config["default_ai"]) if config["default_ai"] in ai_options else 0
            selected_ai = st.selectbox("Select AI Provider", ai_options, index=default_index)
            
            if selected_ai != config["default_ai"]:
                config["default_ai"] = selected_ai
                save_config(config)
    
    # Main content area
    st.markdown('<h1 class="main-header">Dealership Report Parser</h1>', unsafe_allow_html=True)
    st.markdown('<p class="info-text">Upload dealership reports to extract KPIs and generate email summaries.</p>', unsafe_allow_html=True)
    
    # Get current month and year for report
    current_date = datetime.now()
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    
    # Report month selection
    col1, col2 = st.columns(2)
    with col1:
        selected_month = st.selectbox("Report Month", 
                                       months, 
                                       index=current_date.month - 1)
    with col2:
        selected_year = st.selectbox("Report Year", 
                                      range(current_date.year - 2, current_date.year + 1), 
                                      index=2)
    
    # File uploader for multiple files
    uploaded_files = st.file_uploader("Upload PPTX Dealership Reports", 
                                       type=["pptx"], 
                                       accept_multiple_files=True)
    
    if uploaded_files and selected_ai:
        # Get the appropriate API key
        if selected_ai == "claude":
            api_key = config["claude_api_key"]
        elif selected_ai == "openai":
            api_key = config["openai_api_key"]
        else:  # deepseek
            api_key = config["deepseek_api_key"]
        
        # Process button
        if st.button("Process Reports"):
            if not api_key:
                st.error(f"No API key found for {selected_ai}. Please add your API key in the configuration.")
            else:
                # Create a progress bar
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                # Process each file
                results = []
                for i, uploaded_file in enumerate(uploaded_files):
                    progress_text.text(f"Processing {uploaded_file.name}...")
                    
                    try:
                        # Extract text from PPTX
                        extracted_text, _ = extract_text_from_pptx(uploaded_file)
                        
                        # Extract KPIs using AI
                        progress_text.text(f"Extracting KPIs from {uploaded_file.name}...")
                        kpis = extract_kpis_with_ai(api_key, extracted_text, selected_ai)
                        
                        # Generate email template
                        progress_text.text(f"Generating email for {uploaded_file.name}...")
                        email_content = generate_email(kpis, f"{selected_month} {selected_year}")
                        
                        # Add to results
                        results.append({
                            "filename": uploaded_file.name,
                            "kpis": kpis,
                            "email": email_content
                        })
                        
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                    
                    # Update progress
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)
                    progress_text.text(f"Processed {i + 1} of {len(uploaded_files)} files")
                
                # Clear progress indicators
                progress_bar.empty()
                progress_text.empty()
                
                # Display results
                st.success(f"Successfully processed {len(results)} reports!")
                
                # Display each result in an expandable card
                for result in results:
                    with st.expander(f"Report: {result['filename']}"):
                        st.markdown(f"### KPIs Extracted")
                        
                        # Display the store name
                        store_name = result['kpis'].get('store_name', 'Unknown Dealership')
                        st.markdown(f"**Dealership:** {store_name}")
                        st.markdown(f"**Date Range:** {result['kpis'].get('date_range', 'Unknown')}")
                        
                        # Create columns for different metric groups
                        col1, col2 = st.columns(2)
                        
                        # Display RSA/Search metrics
                        if any(k.startswith('rsa_') for k in result['kpis']):
                            with col1:
                                st.markdown("#### Google Search (RSA)")
                                st.markdown(f"Impressions: {result['kpis'].get('rsa_impr', '[x,xxx]')}")
                                st.markdown(f"Clicks: {result['kpis'].get('rsa_clicks', '[xxx]')}")
                                st.markdown(f"CPC: {result['kpis'].get('rsa_cpc', '$x.xx')}")
                                st.markdown(f"Conversions: {result['kpis'].get('rsa_conv', '[xx]')}")
                                st.markdown(f"Cost/Conv: {result['kpis'].get('rsa_cost_conv', '$x.xx')}")
                        
                        # Display PMAX metrics (if they're not identical to VLA metrics)
                        if any(k.startswith('pmax_') and not k.startswith('pmax_vla_') for k in result['kpis']) and not are_pmax_and_vla_identical(result['kpis']):
                            with col2:
                                st.markdown("#### Performance Max")
                                st.markdown(f"Impressions: {result['kpis'].get('pmax_impr', '[x,xxx]')}")
                                st.markdown(f"Clicks: {result['kpis'].get('pmax_clicks', '[xxx]')}")
                                st.markdown(f"CPC: {result['kpis'].get('pmax_cpc', '$x.xx')}")
                                st.markdown(f"Conversions: {result['kpis'].get('pmax_conv', '[xx]')}")
                                st.markdown(f"Cost/Conv: {result['kpis'].get('pmax_cost_conv', '$x.xx')}")
                        
                        # Add more metric groups in new rows
                        col3, col4 = st.columns(2)
                        
                        # Display PMAX VLA metrics
                        if any(k.startswith('pmax_vla_') for k in result['kpis']):
                            with col3:
                                st.markdown("#### Performance Max w/ VLA")
                                st.markdown(f"Impressions: {result['kpis'].get('pmax_vla_impr', '[x,xxx]')}")
                                st.markdown(f"Clicks: {result['kpis'].get('pmax_vla_clicks', '[xxx]')}")
                                st.markdown(f"CPC: {result['kpis'].get('pmax_vla_cpc', '$x.xx')}")
                                st.markdown(f"Conversions: {result['kpis'].get('pmax_vla_conv', '[xx]')}")
                                st.markdown(f"Cost/Conv: {result['kpis'].get('pmax_vla_cost_conv', '$x.xx')}")
                        
                        # Display Social metrics
                        if any(k.startswith('social_') for k in result['kpis']):
                            with col4:
                                st.markdown("#### Social Ads")
                                st.markdown(f"Reach: {result['kpis'].get('social_reach', '[x,xxx]')}")
                                st.markdown(f"Impressions: {result['kpis'].get('social_impr', '[x,xxx]')}")
                                st.markdown(f"Clicks: {result['kpis'].get('social_clicks', '[xxx]')}")
                                st.markdown(f"CPC: {result['kpis'].get('social_cpc', '$x.xx')}")
                                st.markdown(f"VDP Views: {result['kpis'].get('social_vdp', '[xxx]')}")
                        
                        # Display Video metrics if present
                        col5, col6 = st.columns(2)
                        if any(k.startswith('dv_') for k in result['kpis']):
                            with col5:
                                st.markdown("#### Video Campaigns")
                                st.markdown(f"Views: {result['kpis'].get('dv_views', '[x,xxx]')}")
                                st.markdown(f"View Rate: {result['kpis'].get('dv_viewrate', '[xx.xx%]')}")
                                st.markdown(f"CPC: {result['kpis'].get('dv_cpc', '$x.xx')}")
                                st.markdown(f"CPM: {result['kpis'].get('dv_cpm', '$x.xx')}")
                        
                        # Display BCDF metrics if present
                        if result['kpis'].get('has_bcdf', False):
                            with col6:
                                st.markdown("#### BCDF Program")
                                
                                # Display tactics in a more readable format
                                tactics_text = "Unknown"
                                if 'bcdf_tactics_organized' in result['kpis'] and 'tactics_list' in result['kpis']['bcdf_tactics_organized']:
                                    tactics_text = result['kpis']['bcdf_tactics_organized']['tactics_list']
                                else:
                                    tactics_text = str(result['kpis'].get('bcdf_tactics', 'None'))
                                
                                st.markdown(f"Tactics: {tactics_text}")
                                st.markdown(f"Impressions: {result['kpis'].get('bcdf_impr', '[x,xxx]')}")
                                st.markdown(f"Clicks: {result['kpis'].get('bcdf_clicks', '[xxx]')}")
                                st.markdown(f"CPC: {result['kpis'].get('bcdf_cpc', '$x.xx')}")
                                st.markdown(f"VDP Views: {result['kpis'].get('bcdf_vdp', '[xxx]')}")
                        
                        # Email Preview and Download
                        st.markdown("### Email Preview")
                        email_tab1, email_tab2 = st.tabs(["Formatted HTML", "Plain Text"])
                        
                        with email_tab1:
                            st.components.v1.html(result['email']['html'], height=500, scrolling=True)
                            
                            # Add download link for HTML email
                            email_filename_html = f"{store_name.replace(' ', '_')}_{selected_month}_{selected_year}_email.html"
                            download_link_html = get_download_link(result['email']['html'], email_filename_html, "Download HTML Email", is_html=True)
                            st.markdown(download_link_html, unsafe_allow_html=True)
                        
                        with email_tab2:
                            st.text_area("Email Content (Plain Text)", result['email']['plain'], height=300)
                            
                            # Add download link for plain text email
                            email_filename_txt = f"{store_name.replace(' ', '_')}_{selected_month}_{selected_year}_email.txt"
                            download_link_txt = get_download_link(result['email']['plain'], email_filename_txt, "Download Plain Text Email")
                            st.markdown(download_link_txt, unsafe_allow_html=True)
                        
                        # Add download link for KPIs as JSON
                        kpis_json = json.dumps(result['kpis'], indent=2)
                        kpis_filename = f"{store_name.replace(' ', '_')}_{selected_month}_{selected_year}_kpis.json"
                        kpis_download_link = get_download_link(kpis_json, kpis_filename, "Download KPIs as JSON")
                        st.markdown(kpis_download_link, unsafe_allow_html=True)
                
                # Batch download option (if multiple reports)
                if len(results) > 1:
                    st.markdown("### Batch Downloads")
                    
                    # Create a text file with all plain text emails
                    all_emails_plain = "\n".join(["=" * 40 + f"\n{r['filename']}\n" + "=" * 40 + f"\n{r['email']['plain']}\n\n" for r in results])
                    batch_email_link_plain = get_download_link(all_emails_plain, f"all_emails_{selected_month}_{selected_year}.txt", "Download All Plain Text Emails")
                    st.markdown(batch_email_link_plain, unsafe_allow_html=True)
                    
                    # Create an HTML file with all HTML emails
                    all_emails_html = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>All Dealership Reports</title>
                        <style>
                            body { font-family: Arial, sans-serif; }
                            .email-container { margin-bottom: 50px; border-bottom: 2px solid #ddd; padding-bottom: 30px; }
                            h2 { color: #2c3e50; }
                        </style>
                    </head>
                    <body>
                    """
                    for r in results:
                        store = r['kpis'].get('store_name', 'Unknown Dealership')
                        all_emails_html += f"""
                        <div class="email-container">
                            <h2>{store} - {r['filename']}</h2>
                            {r['email']['html']}
                        </div>
                        """
                    all_emails_html += """
                    </body>
                    </html>
                    """
                    
                    batch_email_link_html = get_download_link(all_emails_html, f"all_emails_{selected_month}_{selected_year}.html", "Download All HTML Emails", is_html=True)
                    st.markdown(batch_email_link_html, unsafe_allow_html=True)
                    
                    # Create a combined JSON with all KPIs
                    all_kpis = {r['filename']: r['kpis'] for r in results}
                    all_kpis_json = json.dumps(all_kpis, indent=2)
                    batch_kpis_link = get_download_link(all_kpis_json, f"all_kpis_{selected_month}_{selected_year}.json", "Download All KPIs")
                    st.markdown(batch_kpis_link, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
