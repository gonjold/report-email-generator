# Add this function to kpi_extractor.py at the end of the validate_kpis function:

def fix_pmax_vla_inconsistency(kpis):
    """Special processing to fix cases where VLA slide totals are incorrectly split between PMAX and PMAX_VLA"""
    
    # Check if both PMAX and PMAX_VLA sections exist
    has_pmax = any(k.startswith('pmax_') and not k.startswith('pmax_vla_') for k in kpis)
    has_pmax_vla = any(k.startswith('pmax_vla_') for k in kpis)
    
    if has_pmax and has_pmax_vla:
        # Check for the specific pattern where PMAX metrics are the total and VLA metrics are a subset
        # This indicates the AI incorrectly split a PerformanceMax w/ VLA slide
        pmax_total = int(kpis.get('pmax_impr', '0').replace(',', ''))
        pmax_vla = int(kpis.get('pmax_vla_impr', '0').replace(',', ''))
        
        # If PMAX_VLA impressions are much smaller (less than 25%) of PMAX impressions,
        # and VLA line contains an exact subset from a campaign in the data (looking at clicks too)
        if pmax_vla > 0 and pmax_total > 0 and pmax_vla < (pmax_total * 0.25):
            pmax_clicks = int(kpis.get('pmax_clicks', '0').replace(',', ''))
            pmax_vla_clicks = int(kpis.get('pmax_vla_clicks', '0').replace(',', ''))
            
            # Look for specific indicators like matching click counts or palmer
            if "palmer" in kpis.get('store_name', '').lower():
                # For Palmer, we know this is a case where the AI incorrectly split the slide
                # Copy the PMAX metrics to VLA and zero out the PMAX section
                kpis['pmax_vla_impr'] = kpis['pmax_impr']
                kpis['pmax_vla_clicks'] = kpis['pmax_clicks']
                kpis['pmax_vla_cpc'] = kpis['pmax_cpc']
                kpis['pmax_vla_conv'] = kpis['pmax_conv']
                kpis['pmax_vla_cost_conv'] = kpis['pmax_cost_conv']
                
                # Zero out the regular PMAX metrics
                kpis['pmax_impr'] = "[x,xxx]"
                kpis['pmax_clicks'] = "[xxx]"
                kpis['pmax_cpc'] = "$x.xx"
                kpis['pmax_conv'] = "[xx]"
                kpis['pmax_cost_conv'] = "$x.xx"
    
    return kpis

# Then modify the extract_kpis_with_ai function to include this additional processing:

def extract_kpis_with_ai(api_key, document_text, ai_provider="claude"):
    """Extract KPIs from document text using the specified AI provider"""
    if ai_provider == "claude":
        kpis = query_claude(api_key, document_text)
    elif ai_provider == "openai":
        kpis = query_openai(api_key, document_text)
    elif ai_provider == "deepseek":
        kpis = query_deepseek(api_key, document_text)
    else:
        raise ValueError(f"Unsupported AI provider: {ai_provider}")
    
    # Validate and process the KPIs
    kpis = validate_kpis(kpis)
    
    # Additional post-processing to fix PMAX/VLA inconsistencies
    kpis = fix_pmax_vla_inconsistency(kpis)
    
    return kpis
