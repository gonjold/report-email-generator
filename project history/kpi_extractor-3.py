import json
import re
import requests
import time
import anthropic
import openai

# System prompt for AI extraction with detailed instructions
SYSTEM_PROMPT = """
You are an expert at extracting specific metrics from dealership marketing reports.

Extract the following KPIs from the provided dealership report:
- store_name - The COMPLETE dealership name (make sure to include all brands like "Ram" if present)
- date_range - The date range of the report (format MM/DD/YYYY - MM/DD/YYYY)
- rsa_impr - Impressions from the RSA/Search section
- rsa_clicks - Clicks from the RSA/Search section
- rsa_cpc - Cost Per Click from RSA/Search section (format $X.XX)
- rsa_conv - Conversions from RSA/Search section
- rsa_cost_conv - Cost per Conversion from RSA/Search section (format $X.XX)
- pmax_impr - Impressions from ALL regular PerformanceMax campaigns (not VLA) in the PMAX section
- pmax_clicks - Clicks from ALL regular PerformanceMax campaigns (not VLA) in the PMAX section
- pmax_cpc - Cost Per Click for ALL regular PerformanceMax campaigns (not VLA) (format $X.XX)
- pmax_conv - Conversions from ALL regular PerformanceMax campaigns (not VLA)
- pmax_cost_conv - Cost per Conversion for ALL regular PerformanceMax campaigns (not VLA) (format $X.XX)
- pmax_vla_impr - Impressions from PerformanceMax w/ VLA section (use TOTALS from the slide, not just VLA campaign lines)
- pmax_vla_clicks - Clicks from PerformanceMax w/ VLA section (use TOTALS from the slide, not just VLA campaign lines)
- pmax_vla_cpc - Cost Per Click from PerformanceMax w/ VLA section (format $X.XX) (use TOTALS)
- pmax_vla_conv - Conversions from PerformanceMax w/ VLA section (use TOTALS)
- pmax_vla_cost_conv - Cost per Conversion from PerformanceMax w/ VLA section (format $X.XX) (use TOTALS)
- dv_views - Video Views from the Display/Video or Video Campaigns section
- dv_viewrate - View Rate from the Video section (format XX.XX%)
- dv_cpc - Cost Per Click from the Video section (format $X.XX)
- dv_cpm - Cost Per Mille from the Video section (format $X.XX)
- social_reach - Reach from the Social Ads Summary section
- social_impr - Impressions from the Social Ads Summary section
- social_clicks - Clicks from the Social Ads Summary section
- social_cpc - Cost Per Click from the Social Ads Summary section (format $X.XX)
- social_vdp - VDP Views from the Social Ads Summary or Social Campaigns section
- has_bcdf - Boolean (true/false) indicating if BCDF Program is mentioned in the report

If has_bcdf is true, also extract:
- bcdf_tactics - ACTUAL campaign names from the BCDF section (do not use default values)
- bcdf_impr - TOTAL Impressions from ALL BCDF campaigns (Google + Facebook combined)
- bcdf_clicks - TOTAL Clicks from ALL BCDF campaigns (Google + Facebook combined)
- bcdf_cpc - Average Cost Per Click across all BCDF campaigns (format $X.XX)
- bcdf_conv - Conversions from BCDF section (if available)
- bcdf_vdp - VDP Views from BCDF Facebook campaigns (if available)

Pay special attention to the following hints:
1. The document is structured with SLIDE markers followed by TYPE markers that indicate the content type
2. Look for lines starting with "METRIC:" as these highlight important metrics
3. For the store_name, look at the INTRO slide, usually in the TITLE section
4. For missing values, use placeholders: "[x,xxx]" for impressions, "[xxx]" for clicks, "$x.xx" for costs, "[xx]" for conversions, "[xx.xx%]" for rates
5. The search/RSA metrics are in the SEARCH_OVERVIEW section
6. The regular PerformanceMax metrics are in the PMAX section
7. CRITICAL: If a slide is typed as PMAX_VLA ("PerformanceMax w/ VLA"), use the TOTAL metrics from that entire slide for pmax_vla_* fields, not just the individual VLA campaign line metrics
8. Social metrics are in the SOCIAL_SUMMARY section
9. Video metrics are in the VIDEO section - ONLY include video metrics if they are actually present in the report
10. BCDF information is in the BCDF section
11. Remove any thousand separators (commas) in numeric values
12. CRITICAL: For PMAX_VLA metrics, use the TOTAL metrics from the PMAX_VLA slide, even if that slide contains both regular PMAX and VLA campaigns
13. PMAX metrics should come from a separate slide that is only about regular PMAX campaigns, not from a slide that is labeled PMAX_VLA
14. CRITICAL: For BCDF, you MUST combine metrics from both Google Ads and Facebook Ads campaigns
15. Make sure to extract the correct cost per conversion for VLA campaigns - it's usually different from overall PMAX

Return ONLY a JSON object with these KPIs, nothing else.
"""

def query_claude(api_key, document_text):
    """Send document text to Claude API and get KPIs back"""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        user_prompt = f"""
        Here is the dealership report text to extract KPIs from:
        
        {document_text}
        
        Extract the KPIs as JSON according to the instructions. Pay special attention to:
        1. Include the full, complete store name
        2. BCDF metrics should combine BOTH Google Ads and Facebook Ads campaigns 
        3. Only include Video metrics if they actually exist in the report
        4. For PerformanceMax w/ VLA, use the TOTAL metrics from the slide, not just the individual VLA campaign line metrics
        """
        
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Extract JSON from the response
        response_text = response.content[0].text
        
        # Try different methods to parse the JSON
        try:
            # Try to parse directly if the response is clean JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If not clean JSON, try to extract it from the text
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                # One more attempt without code blocks
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                else:
                    raise Exception("Failed to extract JSON from Claude's response")
    except Exception as e:
        raise Exception(f"Error querying Claude API: {str(e)}")

def query_openai(api_key, document_text):
    """Send document text to OpenAI API and get KPIs back"""
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Add additional instructions focused on key issues
        user_content = f"""
        Here is the dealership report text to extract KPIs from:
        
        {document_text}
        
        IMPORTANT EXTRACTION NOTES:
        1. Make sure to extract the COMPLETE dealership name, including "Ram" if present
        2. For BCDF, combine metrics from BOTH Google Ads and Facebook Ads campaigns
        3. DO NOT include video metrics if they don't exist in the report
        4. For PerformanceMax w/ VLA slides, use the TOTAL metrics for the entire slide, not just the metrics from individual VLA campaign lines
        """
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise Exception(f"Error querying OpenAI API: {str(e)}")

def query_deepseek(api_key, document_text):
    """Send document text to DeepSeek API and get KPIs back with retry logic"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Limit content size for DeepSeek (their API has size limitations)
    max_content_size = 50000
    if len(document_text) > max_content_size:
        document_text = document_text[:max_content_size] + "\n[Document truncated due to size limits]"
    
    # Add additional instructions focused on key issues
    user_content = f"""
    Carefully extract the KPIs from this dealership report:
    
    {document_text}
    
    CRITICAL EXTRACTION NOTES:
    1. Store name MUST include all brands (e.g., include "Ram" if in the dealership name)
    2. BCDF metrics MUST combine both Google Ads and Facebook Ads data
    3. DO NOT include video metrics section if not present in the report
    4. For PerformanceMax w/ VLA slides, use the TOTAL metrics from the slide, not just individual VLA campaign lines
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"}
    }
    
    # Try up to 3 times with backoff
    for attempt in range(3):
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60  # Add timeout
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                try:
                    return json.loads(resp_json["choices"][0]["message"]["content"])
                except json.JSONDecodeError:
                    # Try to extract JSON from text
                    content = resp_json["choices"][0]["message"]["content"]
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            if attempt < 2:  # Not the last attempt yet
                                delay = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                                time.sleep(delay)
                                continue
                            else:
                                raise Exception("Failed to parse JSON from DeepSeek response")
                    else:
                        if attempt < 2:  # Not the last attempt yet
                            delay = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                            time.sleep(delay)
                            continue
                        else:
                            raise Exception("Failed to find JSON in DeepSeek response")
            else:
                if attempt < 2:  # Not the last attempt yet
                    delay = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                    time.sleep(delay)
                else:
                    raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")
        except Exception as e:
            if attempt < 2:  # Not the last attempt yet
                delay = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                time.sleep(delay)
            else:
                raise Exception(f"Error querying DeepSeek API: {str(e)}")
    
    # If we've reached here, all attempts failed
    raise Exception("Failed to get a valid response from DeepSeek after multiple attempts")

def organize_bcdf_tactics(kpis):
    """Process BCDF campaign names to extract and organize by tactics"""
    if not kpis.get('has_bcdf', False) or 'bcdf_tactics' not in kpis:
        return kpis
    
    # Get the raw tactics list
    raw_tactics = kpis['bcdf_tactics']
    
    # If tactics is already a string, convert to list
    if isinstance(raw_tactics, str):
        if raw_tactics.startswith('[') and raw_tactics.endswith(']'):
            try:
                # Try to eval the string to get a proper list
                raw_tactics = eval(raw_tactics)
            except:
                # If eval fails, just split by commas
                raw_tactics = raw_tactics.strip('[]').split(', ')
    
    # Ensure we have a list
    if not isinstance(raw_tactics, list):
        raw_tactics = [raw_tactics]
    
    # Clean up tactic names and categorize
    tactics = {
        'pmax': [],
        'paid_social': [],
        'other': []
    }
    
    for tactic in raw_tactics:
        tactic_name = str(tactic).replace('CAMPAIGN: ', '').strip()
        
        if 'PMAX' in tactic_name.upper():
            tactics['pmax'].append(tactic_name)
        elif 'AIA' in tactic_name.upper() or 'SOCIAL' in tactic_name.upper():
            tactics['paid_social'].append(tactic_name)
        else:
            tactics['other'].append(tactic_name)
    
    # Update the KPIs with organized tactics
    kpis['bcdf_tactics_organized'] = {
        'pmax': len(tactics['pmax']) > 0,
        'paid_social': len(tactics['paid_social']) > 0,
        'tactics_list': ', '.join([
            'Performance Max' if len(tactics['pmax']) > 0 else '',
            'Paid Social' if len(tactics['paid_social']) > 0 else '',
            'Other' if len(tactics['other']) > 0 else ''
        ]).replace(', ,', ',').replace(',,', ',').strip(',').strip(', ')
    }
    
    return kpis

def validate_kpis(kpis):
    """Validate and fix common issues with extracted KPIs"""
    processed_kpis = kpis.copy()
    
    # Fix store name if needed (ensure it includes "Ram")
    if "store_name" in processed_kpis and "Palmer" in processed_kpis["store_name"]:
        if "Chrysler" in processed_kpis["store_name"] and "Dodge" in processed_kpis["store_name"] and "Jeep" in processed_kpis["store_name"]:
            if "Ram" not in processed_kpis["store_name"]:
                processed_kpis["store_name"] = processed_kpis["store_name"] + " Ram"
    
    # Fix numeric formatting issues
    for key in processed_kpis:
        if isinstance(processed_kpis[key], str):
            # Remove commas from numeric values
            if re.search(r'^\d{1,3}(,\d{3})+$', processed_kpis[key]):
                processed_kpis[key] = processed_kpis[key].replace(',', '')
    
    # Fix BCDF data
    if processed_kpis.get("has_bcdf", False):
        # Ensure we have bcdf_tactics
        if "bcdf_tactics" not in processed_kpis or not processed_kpis["bcdf_tactics"]:
            processed_kpis["bcdf_tactics"] = "Unknown BCDF Campaigns"
        
        # Organize BCDF tactics by type
        processed_kpis = organize_bcdf_tactics(processed_kpis)
    
    # Calculate VLA cost per conversion if missing
    if ("pmax_vla_cpc" in processed_kpis and 
        "pmax_vla_clicks" in processed_kpis and 
        "pmax_vla_conv" in processed_kpis and 
        ("pmax_vla_cost_conv" not in processed_kpis or "x" in processed_kpis["pmax_vla_cost_conv"])):
        
        try:
            vla_cpc = float(processed_kpis["pmax_vla_cpc"].replace("$", "").replace(",", ""))
            vla_clicks = int(processed_kpis["pmax_vla_clicks"].replace(",", ""))
            vla_conv = int(processed_kpis["pmax_vla_conv"].replace(",", ""))
            
            if vla_conv > 0:
                vla_cost = vla_cpc * vla_clicks
                cost_per_conv = vla_cost / vla_conv
                processed_kpis["pmax_vla_cost_conv"] = f"${cost_per_conv:.2f}"
        except (ValueError, TypeError, AttributeError):
            pass
    
    # Remove video metrics if they're just placeholders
    has_real_video = False
    for key in ["dv_views", "dv_viewrate", "dv_cpc", "dv_cpm"]:
        if key in processed_kpis and "x" not in str(processed_kpis[key]) and "[" not in str(processed_kpis[key]):
            has_real_video = True
            break
    
    if not has_real_video:
        for key in ["dv_views", "dv_viewrate", "dv_cpc", "dv_cpm"]:
            if key in processed_kpis:
                processed_kpis.pop(key)
    
    return processed_kpis

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
    
    return kpis
