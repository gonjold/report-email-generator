"""
email_generator.py – 2025‑04‑23
--------------------------------
• Gmail‑friendly HTML (minimal formatting)
• Section rows render ONLY when the metric has a real value
• Includes DV View‑through Rate and CPM
• Clean labels (Impressions, Conversions, Cost per Conversion, etc.)
• Simplified greeting and sign-off
• BCDF tactics appear after heading and before KPIs
"""

from __future__ import annotations
import locale
from typing import Any, Dict, List, Tuple, Optional

locale.setlocale(locale.LC_ALL, "")
_CURRENCY = ("cpc", "cpm", "cost_conv", "cost", "cpl", "cpa", "cpv")

# =======================  REPLACE the helper section  =======================
def _placeholder(val: Any) -> bool:
    if val is None: return True
    if isinstance(val, list):                       # NEW – handle list metrics
        return all(_placeholder(v) for v in val)
    s = str(val).strip().lower()
    if s in ("", "none", "nan"):        return True
    if s.startswith("[") or s.startswith("$x") or "x,xxx" in s:  return True
    try:  return float(s) == 0
    except (ValueError, TypeError): return False

def _numeric_from(val: Any) -> Optional[float]:
    """First numeric value from val (supports lists)."""
    if isinstance(val, list):
        for v in val:
            n = _numeric_from(v)
            if n is not None: return n
        return None
    try: return float(val)
    except (TypeError, ValueError): return None

def _fmt_num(num: float, cur: bool) -> str:
    out = f"{num:,.2f}" if not num.is_integer() else f"{num:,.0f}"
    return f"${out}" if cur else out

def _fmt_val(key: str, val: Any) -> str:
    if _placeholder(val): return ""
    # lists → take first usable value (Palmer BCDF arrays)
    if isinstance(val, list): val = _numeric_from(val)
    if val is None: return ""
    if "viewrate" in key.lower():                  # NEW – VTR gets a %
        try: return f"{float(val):.2f}%"
        except (TypeError, ValueError): return str(val)
    try:
        n = float(val)
        return _fmt_num(n, any(t in key.lower() for t in _CURRENCY))
    except (TypeError, ValueError):
        return str(val)
# ===========================================================================


def _any_real(kpis:Dict[str,Any], keys:List[str])->bool:
    return any(not _placeholder(kpis.get(k)) for k in keys)

def _has(prefix:str,k:Dict[str,Any])->bool:
    keys=[m for m in k if m.startswith(prefix) and any(t in m for t in ("impr","clicks","cpc","conv"))]
    return _any_real(k,keys)

def _has_video(k:Dict[str,Any])->bool:
    return _any_real(k,["dv_views","dv_viewrate","dv_cpc","dv_cpm"])

def _pmax_same(k:Dict[str,Any])->bool:
    if not (_has("pmax_",k) and _has("pmax_vla_",k)):
        return False
    met=("impr","clicks","cpc","conv","cost_conv")
    return all(k.get(f"pmax_{m}")==k.get(f"pmax_vla_{m}") for m in met)

# ---------------------------------------------------------------- section builders
def _section(title:str, rows:List[Tuple[str,str]], k:Dict[str,Any])->str:
    lines=[]
    for lbl,key in rows:
        val=_fmt_val(key,k.get(key))
        if val:
            lines.append(f"    <li>{lbl}: {val}</li>")
    if not lines:
        return ""
    body="\n".join(lines)
    return f"<p><b>{title}</b></p>\n<ul>\n{body}\n</ul>\n"

def _bcdf_html(k:Dict[str,Any])->str:
    if not k.get("has_bcdf"):
        return ""
    
    # Get tactics
    tactics=k.get("bcdf_tactics_organized",{}).get("tactics_list") or \
            ", ".join(k.get("bcdf_tactics",[])) or "Unknown"
    
    # Create the section header and tactics line
    bcdf_header = f"<p><b>BUSINESS CENTER DIRECTED FUNDS (BCDF)</b></p>\n"
    tactics_line = f"<p><i>Tactics: {tactics}</i></p>\n"
    
    # Add the metrics
    rows=[("Impressions","bcdf_impr"),("Clicks","bcdf_clicks"),("Avg. CPC","bcdf_cpc"),
          ("VDP Views","bcdf_vdp"),("Conversions","bcdf_conv")]
    
    lines=[]
    for lbl,key in rows:
        val=_fmt_val(key,k.get(key))
        if val:
            lines.append(f"    <li>{lbl}: {val}</li>")
    
    if not lines:
        return ""
    
    body="\n".join(lines)
    return f"{bcdf_header}{tactics_line}<ul>\n{body}\n</ul>\n"

# ---------------------------------------------------------------- main
def generate_email(kpis:Dict[str,Any], month:str)->Dict[str,str]:
    store=kpis.get("store_name","Unknown Dealership")
    pmax_same=_pmax_same(kpis)

    # build HTML
    html_parts=[f"""<div style="font-family:Arial, sans-serif; color:#000; font-size:12px;">
<p><b>SUBJECT:</b> {month} MTD Digital Marketing Report – {store}</p>
<p>Hello!</p>
<p>Attached is the month‑to‑date performance report for <b>{store}</b>, covering <b>{kpis.get('date_range','[Date Range]')}</b>.</p>
<p><b>KPI Breakdown by Channel:</b></p>
"""]

    # Search
    if _has("rsa_",kpis):
        html_parts.append(_section("GOOGLE SEARCH CAMPAIGNS (RSA)",[
            ("Impressions","rsa_impr"),("Clicks","rsa_clicks"),("Avg. CPC","rsa_cpc"),
            ("Conversions","rsa_conv"),("Cost per Conversion","rsa_cost_conv")],kpis))
    # PMAX
    if _has("pmax_",kpis) and not pmax_same:
        html_parts.append(_section("PERFORMANCEMAX CAMPAIGNS",[
            ("Impressions","pmax_impr"),("Clicks","pmax_clicks"),("Avg. CPC","pmax_cpc"),
            ("Conversions","pmax_conv"),("Cost per Conversion","pmax_cost_conv")],kpis))
    if _has("pmax_vla_",kpis):
        html_parts.append(_section("PERFORMANCEMAX w/ VLA CAMPAIGNS",[
            ("Impressions","pmax_vla_impr"),("Clicks","pmax_vla_clicks"),("Avg. CPC","pmax_vla_cpc"),
            ("Conversions","pmax_vla_conv"),("Cost per Conversion","pmax_vla_cost_conv")],kpis))
    # Demand Gen
    if _has("dg_",kpis):
        html_parts.append(_section("GOOGLE DEMAND GEN CAMPAIGNS",[
            ("Impressions","dg_impr"),("Clicks","dg_clicks"),("CPM","dg_cpm"),("Avg. CPC","dg_cpc"),
            ("Conversions","dg_conv")],kpis))
    # Social
    if _has("social_",kpis):
        html_parts.append(_section("SOCIAL ADS",[
            ("Reach","social_reach"),("Impressions","social_impr"),("Clicks","social_clicks"),
            ("Avg. CPC","social_cpc"),("VDP Views","social_vdp")],kpis))
    # Video / Display
    if _has_video(kpis):
        html_parts.append(_section("VIDEO / DISPLAY CAMPAIGNS",[
            ("Views","dv_views"),("View‑through Rate","dv_viewrate"),
            ("Avg. CPC","dv_cpc"),("CPM","dv_cpm")],kpis))
    # BCDF
    html_parts.append(_bcdf_html(kpis))

    html_parts.append("<p>Thank you,</p></div>")
    html="".join(filter(None,html_parts))

    # plain text mirrors HTML
    plain_lines=[f"SUBJECT: {month} MTD Digital Marketing Report – {store}",
                 "", "Hello!", "",
                 f"Attached is the month‑to‑date performance report for {store}, covering {kpis.get('date_range','[Date Range]')}.",
                 "","KPI Breakdown by Channel:"]
    
    def add_block(title:str, rows:List[Tuple[str,str]]):
        vals=[(lbl,_fmt_val(key,kpis.get(key))) for lbl,key in rows if _fmt_val(key,kpis.get(key))]
        if vals:
            plain_lines.append(""); plain_lines.append(title)
            for lbl,val in vals:
                plain_lines.append(f"- {lbl}: {val}")
    
    # same order as HTML
    add_block("GOOGLE SEARCH CAMPAIGNS (RSA)",
              [("Impressions","rsa_impr"),("Clicks","rsa_clicks"),("Avg. CPC","rsa_cpc"),
               ("Conversions","rsa_conv"),("Cost per Conversion","rsa_cost_conv")])
    
    if not pmax_same:
        add_block("PERFORMANCEMAX CAMPAIGNS",
              [("Impressions","pmax_impr"),("Clicks","pmax_clicks"),("Avg. CPC","pmax_cpc"),
               ("Conversions","pmax_conv"),("Cost per Conversion","pmax_cost_conv")])
    
    add_block("PERFORMANCEMAX w/ VLA CAMPAIGNS",
              [("Impressions","pmax_vla_impr"),("Clicks","pmax_vla_clicks"),("Avg. CPC","pmax_vla_cpc"),
               ("Conversions","pmax_vla_conv"),("Cost per Conversion","pmax_vla_cost_conv")])
    
    add_block("GOOGLE DEMAND GEN CAMPAIGNS",
              [("Impressions","dg_impr"),("Clicks","dg_clicks"),("CPM","dg_cpm"),
               ("Conversions","dg_conv")])
    
    add_block("SOCIAL ADS",
              [("Reach","social_reach"),("Impressions","social_impr"),("Clicks","social_clicks"),
               ("Avg. CPC","social_cpc"),("VDP Views","social_vdp")])
    
    add_block("VIDEO / DISPLAY CAMPAIGNS",
              [("Views","dv_views"),("View‑through Rate","dv_viewrate"),("CPM","dv_cpm")])
    
    # BCDF
    if kpis.get("has_bcdf"):
        tactics=kpis.get("bcdf_tactics_organized",{}).get("tactics_list") or \
                ", ".join(kpis.get("bcdf_tactics",[])) or "Unknown"
        
        plain_lines.append("")
        plain_lines.append("BUSINESS CENTER DIRECTED FUNDS (BCDF)")
        plain_lines.append(f"Tactics: {tactics}")
        
        rows=[("Impressions","bcdf_impr"),("Clicks","bcdf_clicks"),("Avg. CPC","bcdf_cpc"),
              ("VDP Views","bcdf_vdp"),("Conversions","bcdf_conv")]
        
        for lbl,key in rows:
            val=_fmt_val(key,kpis.get(key))
            if val:
                plain_lines.append(f"- {lbl}: {val}")

    plain_lines.extend(["","Thank you,"])
    return {"html": html, "plain": "\n".join(plain_lines)}

# ---------------------------------------------------------------------------
#  Back‑compat shim for legacy imports
# ---------------------------------------------------------------------------
def are_pmax_and_vla_identical(kpis: Dict[str, Any]) -> bool:  # noqa: N802
    return _pmax_same(kpis)
