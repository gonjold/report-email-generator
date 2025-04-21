# Dealership Report Parser

A Streamlit application for extracting KPIs from dealership marketing reports in PPTX format and generating email summaries.

## Features

- Extract key performance metrics from PowerPoint presentations
- Support for multiple AI providers (Claude, OpenAI, DeepSeek)
- Process multiple reports simultaneously
- Generate templated emails with only relevant sections
- Support for various campaign types:
  - Google Search (RSA)
  - Performance Max
  - Performance Max w/ VLA
  - Social Ads
  - Video Campaigns
  - BCDF (Business Center Directed Funds)

## Project Structure

```
dealership-report-parser/
├── app.py                 # Main Streamlit application
├── pptx_extractor.py      # PowerPoint extraction logic
├── kpi_extractor.py       # AI-based KPI extraction
├── email_generator.py     # Email template generation
├── requirements.txt       # Python dependencies
└── parser_config.ini      # Configuration file (created on first run)
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/dealership-report-parser.git
   cd dealership-report-parser
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the application:
   ```
   streamlit run app.py
   ```

## Usage

1. Configure at least one AI provider (Claude, OpenAI, or DeepSeek) by adding your API key in the sidebar.
2. Select the report month and year.
3. Upload one or more PPTX dealership reports.
4. Click "Process Reports" to extract KPIs and generate email templates.
5. View and download results for each report.

## Supported Metrics

- **Store Information**
  - Dealership name
  - Report date range

- **Google Search**
  - Impressions, Clicks, CPC, Conversions, Cost per Conversion

- **Performance Max**
  - Impressions, Clicks, CPC, Conversions, Cost per Conversion

- **Performance Max w/ VLA**
  - Impressions, Clicks, CPC, Conversions, Cost per Conversion

- **Social Ads**
  - Reach, Impressions, Clicks, CPC, VDP Views

- **Video Campaigns**
  - Views, View Rate, CPC, CPM

- **BCDF**
  - Tactics, Impressions, Clicks, CPC, VDP Views, Conversions
