def has_valid_data(kpis, prefix):
    """Check if there are valid metrics with the given prefix (not placeholders)"""
    for key in kpis:
        if key.startswith(prefix) and ('impr' in key or 'clicks' in key or 'cpc' in key or 'conv' in key):
            value = str(kpis[key])
            if '[' not in value and 'x' not in value:
                return True
    return False

def has_valid_video_data(kpis):
    """Check if there are valid video metrics (not placeholders)"""
    for key in ["dv_views", "dv_viewrate", "dv_cpc", "dv_cpm"]:
        if key in kpis and '[' not in str(kpis[key]) and 'x' not in str(kpis[key]):
            return True
    return False

def build_html_section(title, kpis, prefix, metrics=None):
    """Build an HTML-formatted section of the email"""
    if metrics is None:
        metrics = [
            ("Impressions", f"{prefix}impr"),
            ("Clicks", f"{prefix}clicks"),
            ("Avg. CPC", f"{prefix}cpc"),
            ("Conversions", f"{prefix}conv"),
            ("Cost per Conversion", f"{prefix}cost_conv")
        ]
    
    section = f"""
<div style="margin-bottom: 20px;">
    <h3 style="color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">{title}</h3>
    <ul style="list-style-type: disc; padding-left: 20px; margin-top: 5px;">
"""
    
    for label, key in metrics:
        if key in kpis:
            section += f'        <li><strong>{label}:</strong> {kpis[key]}</li>\n'
    
    section += """    </ul>
</div>
"""
    
    return section

def build_bcdf_section(kpis):
    """Build a specially formatted BCDF section with tactic grouping"""
    if not kpis.get('has_bcdf', False):
        return ""
    
    tactics_text = "Unknown"
    if 'bcdf_tactics_organized' in kpis and 'tactics_list' in kpis['bcdf_tactics_organized']:
        tactics_text = kpis['bcdf_tactics_organized']['tactics_list']
    
    section = f"""
<div style="margin-bottom: 20px;">
    <h3 style="color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">BUSINESS CENTER DIRECTED FUNDS (BCDF)</h3>
    <p style="margin-bottom: 10px;"><strong>Tactics:</strong> {tactics_text}</p>
    <ul style="list-style-type: disc; padding-left: 20px; margin-top: 5px;">
"""
    
    # Add metrics
    metrics = [
        ("Impressions", "bcdf_impr"),
        ("Clicks", "bcdf_clicks"),
        ("Avg. CPC", "bcdf_cpc")
    ]
    
    if 'bcdf_vdp' in kpis and kpis['bcdf_vdp'] != '[xxx]':
        metrics.append(("VDP Views", "bcdf_vdp"))
            
    if 'bcdf_conv' in kpis and kpis['bcdf_conv'] != '[xx]':
        metrics.append(("Conversions", "bcdf_conv"))
    
    for label, key in metrics:
        if key in kpis:
            section += f'        <li><strong>{label}:</strong> {kpis[key]}</li>\n'
    
    section += """    </ul>
</div>
"""
    
    return section

def generate_email(kpis, report_month):
    """Generate an HTML-formatted email template with smart section inclusion"""
    # Make sure we have a proper store name
    store_name = kpis.get('store_name', 'Unknown Dealership')
    if "Palmer" in store_name and "Chrysler" in store_name and "Dodge" in store_name and "Jeep" in store_name and "Ram" not in store_name:
        store_name = store_name + " Ram"
        kpis['store_name'] = store_name
    
    # Create both HTML and plain text versions
    html_email = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{report_month} MTD Digital Marketing Report – {store_name}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="margin-bottom: 20px;">
        <h2 style="color: #1a5276;">SUBJECT: {report_month} MTD Digital Marketing Report – {store_name}</h2>
        <p>Hi {kpis.get('client_name', '[Client Name]')},</p>
        <p>Attached is the month-to-date performance report for <strong>{store_name}</strong>, covering <strong>{kpis.get('date_range', '[Date Range]')}</strong>.</p>
        <p>The attached report includes an overview of how your campaigns are pacing so far this month. Let me know if you're available to hop on a quick call to review the metrics, talk through what's working, and align on plans for the rest of the month and what's coming up next.</p>
        <p>Please let me know if you have any questions or if there's anything specific you'd like us to dig deeper into. We'll follow up just to make sure everything's on track and you've got what you need from our side.</p>
    </div>

    <h2 style="color: #1a5276; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin-top: 30px;">KPI Breakdown by Channel</h2>
"""

    # Add RSA (Search) section if valid data exists
    if has_valid_data(kpis, 'rsa_'):
        html_email += build_html_section("GOOGLE SEARCH CAMPAIGNS (RSA)", kpis, 'rsa_')

    # Add PMAX section if valid data exists
    if has_valid_data(kpis, 'pmax_') and not kpis.get('pmax_impr', '').startswith('['):
        html_email += build_html_section("PERFORMANCEMAX CAMPAIGNS", kpis, 'pmax_')

    # Add PMAX VLA section if valid data exists
    if has_valid_data(kpis, 'pmax_vla_'):
        html_email += build_html_section("PERFORMANCEMAX w/ VLA CAMPAIGNS", kpis, 'pmax_vla_')

    # Add Social section if valid data exists
    if has_valid_data(kpis, 'social_'):
        social_metrics = [
            ("Reach", "social_reach"),
            ("Impressions", "social_impr"),
            ("Clicks", "social_clicks"),
            ("Avg. CPC", "social_cpc"),
            ("VDP Views", "social_vdp")
        ]
        html_email += build_html_section("SOCIAL ADS", kpis, 'social_', social_metrics)

    # Add Video section if valid data exists
    if has_valid_video_data(kpis):
        video_metrics = [
            ("Views", "dv_views"),
            ("View Rate", "dv_viewrate"),
            ("Avg. CPC", "dv_cpc"),
            ("CPM", "dv_cpm")
        ]
        html_email += build_html_section("VIDEO CAMPAIGNS", kpis, 'dv_', video_metrics)

    # Add BCDF section if applicable
    if kpis.get('has_bcdf', False) and ('bcdf_impr' in kpis or 'bcdf_clicks' in kpis):
        html_email += build_bcdf_section(kpis)

    # Closing
    html_email += """
    <div style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
        <p>Thank you,<br>
        <strong>[Your Name]</strong><br>
        [Your Title]<br>
        [Your Company]<br>
        [Your Contact Information]</p>
    </div>
</body>
</html>
"""

    # Also create a plain text version for fallback and display in the app
    plain_email = f"""SUBJECT: {report_month} MTD Digital Marketing Report – {store_name}

Hi {kpis.get('client_name', '[Client Name]')},

Attached is the month-to-date performance report for {store_name}, covering {kpis.get('date_range', '[Date Range]')}.

The attached report includes an overview of how your campaigns are pacing so far this month. Let me know if you're available to hop on a quick call to review the metrics, talk through what's working, and align on plans for the rest of the month and what's coming up next.

Please let me know if you have any questions or if there's anything specific you'd like us to dig deeper into. We'll follow up just to make sure everything's on track and you've got what you need from our side.

Here's a KPI breakdown by channel:
"""

    # Add RSA (Search) section to plain text if valid data exists
    if has_valid_data(kpis, 'rsa_'):
        plain_email += "\nGOOGLE SEARCH CAMPAIGNS (RSA)\n"
        plain_email += f"- Impressions: {kpis.get('rsa_impr', '[x,xxx]')}\n"
        plain_email += f"- Clicks: {kpis.get('rsa_clicks', '[xxx]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('rsa_cpc', '$x.xx')}\n"
        plain_email += f"- Conversions: {kpis.get('rsa_conv', '[xx]')}\n"
        plain_email += f"- Cost per Conversion: {kpis.get('rsa_cost_conv', '$x.xx')}\n"

    # Similar sections for other campaign types in plain text...
    # Add PMAX section if valid data exists
    if has_valid_data(kpis, 'pmax_') and not kpis.get('pmax_impr', '').startswith('['):
        plain_email += "\nPERFORMANCEMAX CAMPAIGNS\n"
        plain_email += f"- Impressions: {kpis.get('pmax_impr', '[x,xxx]')}\n"
        plain_email += f"- Clicks: {kpis.get('pmax_clicks', '[xxx]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('pmax_cpc', '$x.xx')}\n"
        plain_email += f"- Conversions: {kpis.get('pmax_conv', '[xx]')}\n"
        plain_email += f"- Cost per Conversion: {kpis.get('pmax_cost_conv', '$x.xx')}\n"

    # Add PMAX VLA section if valid data exists
    if has_valid_data(kpis, 'pmax_vla_'):
        plain_email += "\nPERFORMANCEMAX w/ VLA CAMPAIGNS\n"
        plain_email += f"- Impressions: {kpis.get('pmax_vla_impr', '[x,xxx]')}\n"
        plain_email += f"- Clicks: {kpis.get('pmax_vla_clicks', '[xxx]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('pmax_vla_cpc', '$x.xx')}\n"
        plain_email += f"- Conversions: {kpis.get('pmax_vla_conv', '[xx]')}\n"
        plain_email += f"- Cost per Conversion: {kpis.get('pmax_vla_cost_conv', '$x.xx')}\n"
    
    # Add Social section if valid data exists
    if has_valid_data(kpis, 'social_'):
        plain_email += "\nSOCIAL ADS\n"
        plain_email += f"- Reach: {kpis.get('social_reach', '[x,xxx]')}\n"
        plain_email += f"- Impressions: {kpis.get('social_impr', '[x,xxx]')}\n"
        plain_email += f"- Clicks: {kpis.get('social_clicks', '[xxx]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('social_cpc', '$x.xx')}\n"
        plain_email += f"- VDP Views: {kpis.get('social_vdp', '[xxx]')}\n"
    
    # Add Video section if valid data exists
    if has_valid_video_data(kpis):
        plain_email += "\nVIDEO CAMPAIGNS\n"
        plain_email += f"- Views: {kpis.get('dv_views', '[x,xxx]')}\n"
        plain_email += f"- View Rate: {kpis.get('dv_viewrate', '[xx.xx%]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('dv_cpc', '$x.xx')}\n"
        plain_email += f"- CPM: {kpis.get('dv_cpm', '$x.xx')}\n"
    
    # Add BCDF section with improved formatting
    if kpis.get('has_bcdf', False) and ('bcdf_impr' in kpis or 'bcdf_clicks' in kpis):
        tactics_text = "Unknown"
        if 'bcdf_tactics_organized' in kpis and 'tactics_list' in kpis['bcdf_tactics_organized']:
            tactics_text = kpis['bcdf_tactics_organized']['tactics_list']
        
        plain_email += "\nBUSINESS CENTER DIRECTED FUNDS (BCDF)\n"
        plain_email += f"- Tactics: {tactics_text}\n"
        plain_email += f"- Impressions: {kpis.get('bcdf_impr', '[x,xxx]')}\n"
        plain_email += f"- Clicks: {kpis.get('bcdf_clicks', '[xxx]')}\n"
        plain_email += f"- Avg. CPC: {kpis.get('bcdf_cpc', '$x.xx')}\n"
        
        if 'bcdf_vdp' in kpis and kpis['bcdf_vdp'] != '[xxx]':
            plain_email += f"- VDP Views: {kpis['bcdf_vdp']}\n"
            
        if 'bcdf_conv' in kpis and kpis['bcdf_conv'] != '[xx]':
            plain_email += f"- Conversions: {kpis['bcdf_conv']}\n"

    plain_email += """
Thank you,
[Your Name]
[Your Title]
[Your Company]
[Your Contact Information]
"""

    # Return both versions
    return {
        'html': html_email,
        'plain': plain_email
    }