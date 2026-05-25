#!/usr/bin/env python3
"""
Open Claw Trading Pipeline - Complete System Documentation v3
Generates a comprehensive multi-page PDF using fpdf2.
"""

from fpdf import FPDF
import os
import textwrap
from datetime import datetime

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "Open_Claw_v3_Complete.pdf")

# Color scheme
NAVY = (10, 25, 49)
DARK_BLUE = (19, 41, 75)
ACCENT_BLUE = (41, 98, 255)
LIGHT_BG = (240, 243, 247)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (60, 60, 60)
MED_GRAY = (120, 120, 120)
LIGHT_GRAY = (200, 200, 200)
GREEN = (34, 139, 34)
RED = (200, 50, 50)
ORANGE = (230, 140, 20)


class OCPlatformDoc(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        self.page_num = 0

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MED_GRAY)
        self.cell(0, 6, "OPEN CLAW TRADING PIPELINE - Complete System Documentation v3", align="L")
        self.ln(2)
        self.set_draw_color(*LIGHT_GRAY)
        self.line(10, 14, 200, 14)
        self.ln(6)

    def footer(self):
        if self.page_no() <= 1:
            return
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MED_GRAY)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title, size=16):
        self.set_font("Helvetica", "B", size)
        self.set_text_color(*NAVY)
        self.cell(0, 10, title, ln=True)
        self.set_draw_color(*ACCENT_BLUE)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.set_line_width(0.2)
        self.ln(4)

    def sub_title(self, title, size=12):
        self.set_font("Helvetica", "B", size)
        self.set_text_color(*DARK_BLUE)
        self.cell(0, 8, title, ln=True)
        self.ln(2)

    def body_text(self, text, size=9):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*DARK_GRAY)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bullet(self, text, indent=15, size=9):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*DARK_GRAY)
        x = self.get_x()
        self.cell(indent, 5, "  -")
        self.multi_cell(0, 5, text)
        self.ln(1)

    def code_block(self, text, size=7):
        self.set_fill_color(*LIGHT_BG)
        self.set_font("Helvetica", "", size)
        self.set_text_color(40, 40, 40)
        x = self.get_x()
        w = self.w - 2 * self.l_margin
        self.multi_cell(w, 4, text, fill=True)
        self.ln(3)

    def info_box(self, title, text):
        self.set_fill_color(230, 240, 255)
        self.set_draw_color(*ACCENT_BLUE)
        y_start = self.get_y()
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT_BLUE)
        self.cell(0, 6, title, ln=True, fill=True)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*DARK_GRAY)
        self.multi_cell(0, 4.5, text, fill=True)
        self.ln(3)

    def table_header(self, cols, widths):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        for i, col in enumerate(cols):
            self.cell(widths[i], 7, col, border=1, fill=True, align="C")
        self.ln()

    def table_row(self, cols, widths, fill=False):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*DARK_GRAY)
        if fill:
            self.set_fill_color(*LIGHT_BG)
        else:
            self.set_fill_color(*WHITE)
        for i, col in enumerate(cols):
            self.cell(widths[i], 6, col, border=1, fill=True, align="C")
        self.ln()
def build_cover(pdf):
    """PAGE 1: Cover Page"""
    pdf.add_page()
    # Navy background block
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 297, "F")

    # Title area
    pdf.set_y(50)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 14, "OPEN CLAW", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, "TRADING PIPELINE", ln=True, align="C")
    pdf.ln(6)

    # Accent line
    pdf.set_draw_color(*ACCENT_BLUE)
    pdf.set_line_width(1.5)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(180, 200, 240)
    pdf.cell(0, 8, "Complete System Documentation v3", ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "5-Agent Quantitative Trading Pipeline", ln=True, align="C")
    pdf.cell(0, 6, "for a $10,000 Speculative Spot-Only Account", ln=True, align="C")
    pdf.ln(12)

    # Pipeline flow diagram
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*ACCENT_BLUE)
    pdf.cell(0, 8, "PIPELINE ARCHITECTURE", ln=True, align="C")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(180, 200, 240)

    flow_lines = [
        "+------------------+     +------------------+     +------------------+",
        "| PRE-FLIGHT DATA  | --> | AGENT 1: MACRO   | --> | AGENT 2: SCREEN  |",
        "| yfinance, Asm,   |     | DIRECTOR         |     | FUNDAMENTALS     |",
        "| X API feeds      |     | Regime + Vol     |     | Gemini Deep Res  |",
        "+------------------+     +------------------+     +------------------+",
        "                                                          |",
        "                                                          v",
        "+------------------+     +------------------+     +------------------+",
        "| AGENT 5: MONITOR | <-- | AGENT 4: RISK    | <-- | AGENT 3: SMART   |",
        "| 3:30 PM Review   |     | MANAGER (4A+4B)  |     | MONEY VERIFIER   |",
        "| Hold/Trim/Close  |     | Size + Stops     |     | X/Twitter Sent.  |",
        "+------------------+     +------------------+     +------------------+",
    ]
    for line in flow_lines:
        pdf.cell(0, 4, line, ln=True, align="C")
    pdf.ln(10)

    # v3 Changes Summary
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*ACCENT_BLUE)
    pdf.cell(0, 8, "v3 KEY CHANGES", ln=True, align="C")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(180, 200, 240)

    changes = [
        "- Assembly Private integration for sentiment, macro, risk, sector rotation data",
        "- Hybrid screener universe: 60 static tickers + Assembly dynamic momentum screens",
        "- X API (pay-per-use) with 15 curated smart-money accounts",
        "- Kill-switch relaxation: DIX unavailability no longer forces DEFER",
        "- Sentiment Composite (0-100) integrated into macro analysis",
        "- Full yield curve data from Assembly (2Y/5Y/7Y/10Y/20Y/30Y)",
        "- Sector rotation with relative strength vs SPY",
        "- Risk gauges with trend indicators (VIX, VXN, MOVE, HYG, LQD, JNK)",
    ]
    for c in changes:
        pdf.cell(0, 5, c, ln=True, align="C")
    pdf.ln(10)

    # Footer
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MED_GRAY)
    today = datetime.now().strftime("%B %d, %Y")
    pdf.cell(0, 5, f"Generated: {today}", ln=True, align="C")
    pdf.cell(0, 5, "OCPlatform | Chris Buetti", ln=True, align="C")
def build_toc(pdf):
    """PAGE 2: Table of Contents"""
    pdf.add_page()
    pdf.section_title("TABLE OF CONTENTS", 18)
    pdf.ln(6)

    toc_items = [
        ("1.", "System Overview", "3-4"),
        ("2.", "v3 Change Summary", "5"),
        ("3.", "Pre-Flight Data Layer", "6"),
        ("4.", "Agent 1: Macro Director", "7-9"),
        ("5.", "Agent 2: Fundamental Screener", "10-12"),
        ("6.", "Agent 3: Smart Money Verifier", "13-14"),
        ("7.", "Agent 4: Risk Manager (4A + 4B)", "15-17"),
        ("8.", "Agent 5: Position Monitor", "18-19"),
        ("9.", "Engineering Implementation", "20-21"),
        ("10.", "Screener Universe", "22"),
        ("11.", "Quick Reference", "23"),
    ]

    for num, title, pages in toc_items:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*NAVY)
        pdf.cell(12, 8, num)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*DARK_GRAY)
        pdf.cell(140, 8, title)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*MED_GRAY)
        pdf.cell(0, 8, pages, align="R")
        pdf.ln()
        pdf.set_draw_color(*LIGHT_GRAY)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)
def build_overview(pdf):
    """PAGE 3-4: System Overview"""
    pdf.add_page()
    pdf.section_title("1. SYSTEM OVERVIEW")

    pdf.sub_title("Purpose")
    pdf.body_text(
        "Open Claw is a 5-agent quantitative trading pipeline designed for a $10,000 speculative "
        "spot-only brokerage account. It combines macro regime analysis, fundamental screening with "
        "deep research, smart money sentiment verification via X/Twitter, multiplicative risk sizing, "
        "and automated position monitoring to generate disciplined, data-driven trade ideas."
    )

    pdf.sub_title("Account Constraints")
    pdf.bullet("Account size: $10,000 (spot only, no margin, no options, no futures)")
    pdf.bullet("Maximum risk per session: $500")
    pdf.bullet("Maximum risk per trade: $150")
    pdf.bullet("No overnight leverage")
    pdf.bullet("All stops must be within 10% of entry")
    pdf.ln(2)

    pdf.sub_title("Agent Roles")
    cols = ["Agent", "Name", "Role", "Model"]
    widths = [20, 45, 80, 45]
    pdf.table_header(cols, widths)
    rows = [
        ["1", "Macro Director", "Classify regime, set vol + posture", "Claude Sonnet"],
        ["2", "Fund. Screener", "Select 1-3 candidates, deep research", "Gemini 3.1 Pro"],
        ["3", "Smart Money", "Score X/Twitter sentiment per ticker", "Claude Sonnet"],
        ["4A", "Stop Anchor", "Identify stop levels from technicals", "Claude Sonnet"],
        ["4B", "Risk Sizer", "Multiplicative position sizing (Python)", "Deterministic"],
        ["5", "Pos. Monitor", "3:30 PM review, Hold/Trim/Close", "Claude Sonnet"],
    ]
    for i, row in enumerate(rows):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("Trade Lifecycle")
    pdf.body_text(
        "1. Pre-Flight: Data collection from yfinance, Assembly Private, and X API.\n"
        "2. Agent 1: Reads macro data, classifies regime (RISK-ON / CAUTIOUS / RISK-OFF / CRISIS / DEFER), "
        "sets vol_regime and posture with conviction floor.\n"
        "3. Agent 2: Receives regime directive and screener universe. Performs deep fundamental research "
        "using Gemini 3.1 Pro. Selects 1-3 candidates with conviction scores.\n"
        "4. Agent 3: Verifies each candidate against smart money X/Twitter sentiment using 15 curated "
        "accounts over a 7-day lookback.\n"
        "5. Agent 4A: Identifies stop-loss anchors from MA10/MA20/MA50/20d low. Calculates FINAL_CONVICTION "
        "as average of Agent 2 and Agent 3 scores.\n"
        "6. Agent 4B: Applies multiplicative sizing formula to determine position size and risk budget.\n"
        "7. Agent 5: At 3:30 PM ET, reviews all open positions. Applies trailing stop logic. Decides "
        "HOLD, TRIM, or CLOSE for each position."
    )

    pdf.sub_title("Run Cadence -- Full Schedule")
    cols2 = ["Time (ET)", "Action", "Details"]
    widths2 = [35, 55, 100]
    pdf.table_header(cols2, widths2)
    schedule = [
        ["6:00 AM", "Pre-Flight Data", "yfinance, Assembly scrape, X API"],
        ["6:15 AM", "Agent 1: Macro", "Regime classification"],
        ["6:30 AM", "Agent 2: Screener", "Fundamental deep research"],
        ["7:00 AM", "Agent 3: Smart Money", "X/Twitter sentiment scoring"],
        ["7:15 AM", "Agent 4: Risk", "Stop anchors + position sizing"],
        ["7:30 AM", "Tear Sheet Output", "Final trade recommendations"],
        ["3:30 PM", "Agent 5: Monitor", "Position review with 3:25 snap"],
    ]
    for i, row in enumerate(schedule):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))
def build_v3_changes(pdf):
    """PAGE 5: v3 Change Summary"""
    pdf.add_page()
    pdf.section_title("2. v3 CHANGE SUMMARY")

    pdf.body_text(
        "Version 3 of the Open Claw pipeline introduces significant enhancements across data sourcing, "
        "screening methodology, and kill-switch logic. Below is a comprehensive list of all changes "
        "from v2 to v3."
    )

    pdf.sub_title("Assembly Private Integration")
    pdf.bullet("NEW: Browser-based scraping of Assembly Private (assemblyprivate.com) for institutional-grade data")
    pdf.bullet("Sentiment Composite score (0-100) with sub-components (Retail, Institutional, Options, Dark Pool)")
    pdf.bullet("Cross-asset macro indicators and rotation signals")
    pdf.bullet("Full risk gauge panel: VIX, VXN, MOVE Index, HYG, LQD, JNK with trend arrows")
    pdf.bullet("Sector rotation matrix with Relative Strength vs SPY for all 11 GICS sectors")
    pdf.bullet("Complete yield curve: 2Y, 5Y, 7Y, 10Y, 20Y, 30Y rates with spread calculations")
    pdf.bullet("Momentum screens: top gainers, breakout candidates, unusual volume")
    pdf.ln(2)

    pdf.sub_title("Hybrid Screener Universe")
    pdf.bullet("CHANGED: Screener universe expanded from static-only to hybrid model")
    pdf.bullet("60 static tickers maintained across 8 sectors (tech, semis, fintech, energy, etc.)")
    pdf.bullet("Assembly dynamic tickers added from momentum screens (top gainers, breakouts)")
    pdf.bullet("Dynamic tickers tagged with SOURCE='Assembly Momentum' for traceability")
    pdf.bullet("Deduplication applied when Assembly tickers overlap with static universe")
    pdf.ln(2)

    pdf.sub_title("X API Integration")
    pdf.bullet("CHANGED: Moved from scraping to official X API (search/recent endpoint)")
    pdf.bullet("Pay-per-use tier -- 7-day maximum lookback window")
    pdf.bullet("15 curated smart-money accounts for targeted sentiment analysis")
    pdf.bullet("Structured query building: ticker + cashtag + account mentions")
    pdf.ln(2)

    pdf.sub_title("Kill-Switch Relaxation")
    pdf.bullet("CHANGED: DIX data unavailability no longer forces DEFER regime")
    pdf.bullet("If DIX is missing, Agent 1 MAY proceed but MUST note in missing_data")
    pdf.bullet("DIX unavailability reduces confidence score by 2 points")
    pdf.bullet("MOVE and Credit spread data remain NON-NEGOTIABLE -- missing = DEFER")
    pdf.ln(2)

    pdf.sub_title("Sentiment Composite Integration")
    pdf.bullet("NEW: Assembly Sentiment Composite (0-100) feeds into Agent 1 macro analysis")
    pdf.bullet("Sub-components visible: Retail Flow, Institutional Flow, Options Sentiment, Dark Pool Activity")
    pdf.bullet("Extreme readings (>80 or <20) flagged as potential contrarian signals")
    pdf.ln(2)

    pdf.sub_title("Other Enhancements")
    pdf.bullet("Agent 2 model upgraded to Gemini 3.1 Pro with Deep Research capability")
    pdf.bullet("Pre-flight data collection expanded with fundamental data pre-fetch")
    pdf.bullet("Output format standardized across all agents with ISO timestamps")
    pdf.bullet("Tear sheet format enhanced with Assembly data citations")
def build_preflight(pdf):
    """PAGE 6: Pre-Flight Data Layer"""
    pdf.add_page()
    pdf.section_title("3. PRE-FLIGHT DATA LAYER")

    pdf.body_text(
        "The pre-flight data layer runs at 6:00 AM ET before any agent executes. It collects, "
        "normalizes, and persists all market data that downstream agents consume. No agent makes "
        "third-party API calls -- all data is pre-fetched and passed as context."
    )

    pdf.sub_title("Data Source 1: yfinance")
    pdf.bullet("VIX (^VIX) -- current level, 5d/20d trend")
    pdf.bullet("MOVE Index proxy (via TLT implied vol or direct if available)")
    pdf.bullet("DIX -- Dark Index (scraped from squeezemetrics.com)")
    pdf.bullet("HYG/LQD/JNK -- High yield and credit spread proxies")
    pdf.bullet("SPY, QQQ, IWM -- Major index levels and breadth")
    pdf.bullet("Sector ETFs (XLK, XLF, XLE, XLV, etc.) for rotation analysis")
    pdf.bullet("Per-ticker OHLCV data for screener universe candidates")
    pdf.bullet("Technical indicators: MA10, MA20, MA50, 20-day low for each candidate")
    pdf.ln(2)

    pdf.sub_title("Data Source 2: Assembly Private")
    pdf.bullet("Scraped via browser automation (Playwright/headless Chrome)")
    pdf.bullet("SPA extraction -- Assembly is a single-page app, requires JS rendering")
    pdf.bullet("Data points extracted:")
    pdf.bullet("  -- Sentiment Composite (0-100) with 4 sub-components", indent=20)
    pdf.bullet("  -- Macro indicators: GDP nowcast, inflation expectations, Fed funds probability", indent=20)
    pdf.bullet("  -- Risk gauges: VIX, VXN, MOVE, HYG, LQD, JNK with Up/Down/Flat trends", indent=20)
    pdf.bullet("  -- Sector rotation: all 11 GICS sectors with RS vs SPY", indent=20)
    pdf.bullet("  -- Yield curve: 2Y/5Y/7Y/10Y/20Y/30Y rates, 2s10s and 5s30s spreads", indent=20)
    pdf.bullet("  -- Momentum screens: top gainers, breakout setups, unusual volume", indent=20)
    pdf.bullet("Output: assembly_data.json persisted to pipeline output directory")
    pdf.ln(2)

    pdf.sub_title("Data Source 3: X API (Twitter)")
    pdf.bullet("Endpoint: search/recent (v2 API)")
    pdf.bullet("Tier: Pay-per-use (Basic or Pro depending on volume)")
    pdf.bullet("Lookback: 7 days maximum (API constraint)")
    pdf.bullet("Query construction: '$TICKER OR TICKER' + from:account filters")
    pdf.bullet("Rate limits: 300 requests/15min (Basic), 450/15min (Pro)")
    pdf.bullet("Output: x_sentiment_raw.json with tweet objects per ticker")
    pdf.ln(2)

    pdf.sub_title("Screener Universe Construction")
    pdf.body_text(
        "The hybrid screener combines 60 static tickers (curated across 8 sectors) with dynamic "
        "tickers sourced from Assembly Private momentum screens. Steps:"
    )
    pdf.bullet("1. Load static universe (60 tickers, see Section 10)")
    pdf.bullet("2. Fetch Assembly momentum screens (top gainers, breakouts, unusual volume)")
    pdf.bullet("3. Filter Assembly tickers: must be >$5 share price and >$100M market cap")
    pdf.bullet("4. Merge and deduplicate -- Assembly tickers tagged SOURCE='Assembly Momentum'")
    pdf.bullet("5. Fetch fundamental data for all tickers in merged universe")
    pdf.bullet("6. Output: screener_universe.json with ticker, sector, source, fundamental data")
    pdf.ln(2)

    pdf.sub_title("Fundamental Data Pre-Fetch")
    pdf.body_text("For each ticker in the screener universe, the following are collected via yfinance:")
    cols = ["Metric", "Source", "Usage"]
    widths = [50, 50, 90]
    pdf.table_header(cols, widths)
    metrics = [
        ["P/E Ratio (TTM)", "yfinance", "Valuation screen"],
        ["Forward P/E", "yfinance", "Growth expectations"],
        ["PEG Ratio", "yfinance", "Growth-adjusted value"],
        ["Beta", "yfinance", "Vol modifier input"],
        ["Gross Margin", "yfinance", "Quality filter"],
        ["Operating Margin", "yfinance", "Profitability check"],
        ["Free Cash Flow", "yfinance", "Cash generation"],
        ["Debt/Equity", "yfinance", "Balance sheet risk"],
        ["Market Cap", "yfinance", "Size filter (>$100M)"],
        ["Avg Volume (20d)", "yfinance", "Liquidity check"],
    ]
    for i, row in enumerate(metrics):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.sub_title("Output Files Generated")
    pdf.code_block(
        "output/\n"
        "  macro_data.json          -- VIX, MOVE, DIX, credit, yields\n"
        "  assembly_data.json       -- Full Assembly Private extract\n"
        "  x_sentiment_raw.json     -- Raw X API tweet data\n"
        "  screener_universe.json   -- Merged ticker list + fundamentals\n"
        "  technical_data.json      -- MA10, MA20, MA50, 20d low per ticker\n"
        "  preflight_summary.json   -- Metadata: timestamps, data quality flags"
    )
def build_agent1(pdf):
    """PAGE 7-9: Agent 1 - Macro Director"""
    pdf.add_page()
    pdf.section_title("4. AGENT 1: MACRO DIRECTOR")

    pdf.sub_title("Overview")
    pdf.body_text(
        "Agent 1 is the gate-keeper of the entire pipeline. It reads macro data and classifies "
        "the current market regime into one of five states. It does NOT pick stocks or make trade "
        "recommendations -- it sets the environment that all downstream agents operate within."
    )

    pdf.sub_title("System Prompt (Verbatim)")
    prompt_text = (
        'You are Agent 1: The Macro Director for a $10,000 speculative spot-only trading account.\n\n'
        'YOUR SOLE JOB: Read the macro data provided and classify the current market regime. '
        'You do NOT pick stocks. You do NOT make trade recommendations. You do NOT set position '
        'limits or allocation caps -- that is Agent 4\'s job.\n\n'
        'REGIME CLASSIFICATIONS (pick exactly one):\n'
        '1. RISK-ON -- Bull trend intact, volatility low/falling, spreads tight, dark pool buying strong\n'
        '2. CAUTIOUS RISK-ON -- Generally positive but with yellow flags (elevated VIX, mixed signals)\n'
        '3. RISK-OFF -- Defensive posture. Rising vol, widening spreads, flight to safety underway\n'
        '4. CRISIS -- Extreme stress. VIX >35, MOVE >150, credit markets seizing\n'
        '5. DEFER -- MANDATORY if DIX, MOVE, or Credit data is missing/unavailable.\n\n'
        'KILL-SWITCH RULE (NON-NEGOTIABLE):\n'
        'If MOVE index data OR Credit spread data is "DATA UNAVAILABLE" or missing, you MUST output '
        'REGIME: DEFER.\n'
        'If DIX data is unavailable, you MAY proceed but MUST note it in missing_data and reduce '
        'confidence by 2 points.\n\n'
        'VOL REGIME (MANDATORY OUTPUT -- Agent 4 needs this exact string):\n'
        '- COMPRESSED: VIX < 14 AND MOVE < 90\n'
        '- NORMAL: VIX 14-20 AND MOVE 90-120\n'
        '- ELEVATED: VIX 20-30 OR MOVE 120-150\n'
        '- STRESSED: VIX > 30 OR MOVE > 150\n\n'
        'POSTURE TABLE:\n'
        '- RISK-ON -> Aggressive, CONVICTION_FLOOR: 5\n'
        '- CAUTIOUS RISK-ON -> Offensive, CONVICTION_FLOOR: 6\n'
        '- RISK-OFF -> Defensive, CONVICTION_FLOOR: 7\n'
        '- CRISIS -> Bunker, CONVICTION_FLOOR: 9\n'
        '- DEFER -> Hold, CONVICTION_FLOOR: 10\n\n'
        'DECISION INPUTS: VIX, MOVE, DIX, Yield curve, HY spread proxy, Sector breadth\n\n'
        'ASSEMBLY PRIVATE DATA (if provided): Sentiment Composite (0-100), sub-components, '
        'cross-asset rotation, risk gauges (VIX, VXN, MOVE, HYG, LQD, JNK with trends), '
        'sector rotation with RS vs SPY, full yield curve.\n\n'
        'Output JSON: agent, timestamp, regime, vol_regime, posture, conviction_floor, '
        'preferred_themes, summary, key_signals, missing_data'
    )
    pdf.code_block(prompt_text)

    pdf.sub_title("Input Contract")
    cols = ["Field", "Source", "Required"]
    widths = [55, 80, 55]
    pdf.table_header(cols, widths)
    inputs = [
        ["VIX level + trend", "yfinance (^VIX)", "YES"],
        ["MOVE Index", "yfinance / Assembly", "YES (kill-switch)"],
        ["DIX", "squeezemetrics.com", "Soft (v3 relaxed)"],
        ["HY Spread (HYG-LQD)", "yfinance", "YES (kill-switch)"],
        ["Yield Curve", "Assembly Private", "NO (enrichment)"],
        ["Sector Breadth", "yfinance sector ETFs", "NO (enrichment)"],
        ["Sentiment Composite", "Assembly Private", "NO (enrichment)"],
        ["Risk Gauges", "Assembly Private", "NO (enrichment)"],
        ["Sector Rotation + RS", "Assembly Private", "NO (enrichment)"],
    ]
    for i, row in enumerate(inputs):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Output Contract")
    cols2 = ["Field", "Type", "Example"]
    widths2 = [50, 40, 100]
    pdf.table_header(cols2, widths2)
    outputs = [
        ["regime", "string (enum)", "CAUTIOUS RISK-ON"],
        ["vol_regime", "string (enum)", "NORMAL"],
        ["posture", "string", "Offensive"],
        ["conviction_floor", "int (0-10)", "6"],
        ["preferred_themes", "string[]", '["AI Infrastructure", "Semis"]'],
        ["summary", "string", "Markets constructive but..."],
        ["key_signals", "string[]", '["VIX 16.2 normal range"]'],
        ["missing_data", "string[]", '["DIX unavailable"]'],
    ]
    for i, row in enumerate(outputs):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))

    # New page for kill-switch detail
    pdf.add_page()
    pdf.sub_title("Kill-Switch Rules (Detail)")
    pdf.info_box(
        "HARD KILL-SWITCH (v2 + v3)",
        "If MOVE index data is 'DATA UNAVAILABLE' or missing --> REGIME: DEFER\n"
        "If Credit spread data (HYG-LQD) is unavailable --> REGIME: DEFER\n"
        "These are NON-NEGOTIABLE. No exceptions. No overrides."
    )
    pdf.info_box(
        "SOFT KILL-SWITCH (v3 CHANGE)",
        "If DIX data is unavailable:\n"
        "  - Agent 1 MAY proceed (not forced to DEFER)\n"
        "  - MUST note 'DIX unavailable' in missing_data array\n"
        "  - MUST reduce confidence by 2 points\n"
        "  - Rationale: DIX is useful but not critical for regime classification"
    )

    pdf.sub_title("Assembly Private Data Integration")
    pdf.body_text(
        "When Assembly Private data is available, Agent 1 receives a rich supplementary dataset. "
        "This data does NOT replace the core inputs (VIX, MOVE, DIX, credit) but enriches the "
        "regime classification with institutional-grade signals."
    )
    pdf.bullet("Sentiment Composite: 0-100 scale. >70 = bullish consensus (potential contrarian warning). "
               "<30 = bearish consensus (potential bottom signal).")
    pdf.bullet("Risk Gauges: VIX, VXN, MOVE, HYG, LQD, JNK with directional trends. Cross-validates "
               "the primary VIX/MOVE readings.")
    pdf.bullet("Sector Rotation: Identifies which sectors are leading/lagging vs SPY. Feeds into "
               "preferred_themes output.")
    pdf.bullet("Yield Curve: 2Y through 30Y rates with spread calculations. Inversion signals feed "
               "into regime assessment.")
    pdf.ln(2)

    pdf.sub_title("Regime Classification Logic")
    pdf.body_text(
        "Agent 1 uses a weight-of-evidence approach. No single indicator forces a regime "
        "(except kill-switch conditions). The model considers:\n\n"
        "RISK-ON requires: VIX <18, MOVE <110, DIX >45%, spreads stable/tightening, "
        "positive breadth, Assembly sentiment >55.\n\n"
        "CAUTIOUS RISK-ON: Generally positive but 1-2 yellow flags. Common triggers: "
        "VIX 18-22, mixed sector breadth, Assembly sentiment 40-55.\n\n"
        "RISK-OFF: Rising vol (VIX >22), widening spreads, MOVE >120, flight-to-safety "
        "rotation visible, Assembly sentiment <40.\n\n"
        "CRISIS: VIX >35, MOVE >150, credit markets dislocating, Assembly sentiment <20."
    )

    pdf.sub_title("Vol Regime Determination")
    cols3 = ["Vol Regime", "VIX Condition", "MOVE Condition", "Agent 4 Impact"]
    widths3 = [35, 40, 40, 75]
    pdf.table_header(cols3, widths3)
    vol_rows = [
        ["COMPRESSED", "< 14", "< 90", "VOL_MOD = 1.2 (larger positions)"],
        ["NORMAL", "14 - 20", "90 - 120", "VOL_MOD = 1.0 (standard)"],
        ["ELEVATED", "20 - 30", "120 - 150", "VOL_MOD = 0.7 (reduced size)"],
        ["STRESSED", "> 30", "> 150", "VOL_MOD = 0.4 (minimal size)"],
    ]
    for i, row in enumerate(vol_rows):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))
    pdf.ln(2)
    pdf.body_text(
        "Note: Vol regime uses OR logic for ELEVATED/STRESSED -- if either VIX or MOVE breaches "
        "the threshold, the higher regime applies. For COMPRESSED and NORMAL, both conditions must "
        "be met (AND logic)."
    )
def build_agent2(pdf):
    """PAGE 10-12: Agent 2 - Fundamental Screener"""
    pdf.add_page()
    pdf.section_title("5. AGENT 2: FUNDAMENTAL SCREENER")

    pdf.sub_title("Overview")
    pdf.body_text(
        "Agent 2 is the stock picker. Given Agent 1's regime directive and a pre-filtered screener "
        "universe with fundamental data, it performs deep quantitative analysis to select 1-3 "
        "high-conviction candidates. It uses Gemini 3.1 Pro with Deep Research capability for "
        "comprehensive fundamental analysis."
    )

    pdf.sub_title("Model: Gemini 3.1 Pro with Deep Research")
    pdf.bullet("Provider: Google GenAI (google-genai SDK)")
    pdf.bullet("Model ID: gemini-3.1-pro (or latest equivalent)")
    pdf.bullet("Deep Research: Enabled -- model performs multi-step web research")
    pdf.bullet("Context window: Extended for comprehensive fundamental analysis")
    pdf.bullet("Temperature: 0.3 (low creativity, high precision for financial analysis)")
    pdf.ln(2)

    pdf.sub_title("System Prompt (Verbatim)")
    prompt_text = (
        'You are Agent 2: The Fundamental Screener for a $10,000 speculative spot-only trading account.\n\n'
        'YOUR JOB: Given Agent 1\'s regime directive, a pre-filtered SCREENER_UNIVERSE, and pre-fetched '
        'FUNDAMENTAL_DATA, select 1-3 candidates through rigorous quantitative analysis.\n\n'
        'CRITICAL RULES:\n'
        '1. Only select from SCREENER_UNIVERSE. Do NOT suggest any ticker not on the list.\n'
        '2. CONVICTION_SCORE must be strict integer 0-10.\n'
        '3. THEME_MATCH must be character-for-character copy from Agent 1.\n'
        '4. SOURCE must be "Newsletter" or "Screener Stage 2".\n'
        '5. Each candidate needs quantitative thesis + specific near-term catalyst.\n'
        '6. If regime is DEFER/CRISIS with Bunker, output empty candidates.\n'
        '7. Only candidates meeting CONVICTION_FLOOR pass.\n\n'
        'Deep Research Protocol: research_scratchpad block required before output.\n'
        'Step 1: Inventory numerical data.\n'
        'Step 2: Verify >$5 and >$100M.\n'
        'Step 3: Argue downside.\n'
        'Step 4: Score 0-10.\n'
        'Step 5: Verify THEME_MATCH verbatim.\n\n'
        'Output JSON: agent, timestamp, regime_received, candidates array, screening_notes'
    )
    pdf.code_block(prompt_text)

    pdf.sub_title("Input Contract")
    cols = ["Field", "Source", "Required"]
    widths = [55, 80, 55]
    pdf.table_header(cols, widths)
    inputs = [
        ["regime", "Agent 1 output", "YES"],
        ["vol_regime", "Agent 1 output", "YES"],
        ["posture", "Agent 1 output", "YES"],
        ["conviction_floor", "Agent 1 output", "YES"],
        ["preferred_themes", "Agent 1 output", "YES"],
        ["screener_universe", "Pre-flight", "YES"],
        ["fundamental_data", "Pre-flight (yfinance)", "YES"],
    ]
    for i, row in enumerate(inputs):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Output Contract")
    cols2 = ["Field", "Type", "Description"]
    widths2 = [50, 40, 100]
    pdf.table_header(cols2, widths2)
    outputs = [
        ["agent", "string", '"Agent 2: Fundamental Screener"'],
        ["timestamp", "string (ISO)", "2025-05-19T06:30:00Z"],
        ["regime_received", "string", "Echo of Agent 1 regime"],
        ["candidates", "array", "1-3 candidate objects"],
        ["screening_notes", "string", "Summary of screening process"],
    ]
    for i, row in enumerate(outputs):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))

    pdf.add_page()
    pdf.sub_title("Candidate Object Schema")
    cols3 = ["Field", "Type", "Constraint"]
    widths3 = [50, 40, 100]
    pdf.table_header(cols3, widths3)
    cand_fields = [
        ["ticker", "string", "Must be in SCREENER_UNIVERSE"],
        ["conviction_score", "int", "0-10, must meet conviction_floor"],
        ["theme_match", "string", "Verbatim from Agent 1 themes"],
        ["source", "string", '"Newsletter" or "Screener Stage 2"'],
        ["thesis", "string", "Quantitative thesis with data"],
        ["catalyst", "string", "Specific near-term catalyst"],
        ["risk_factors", "string[]", "Key downside risks identified"],
        ["research_scratchpad", "string", "Full research notes"],
    ]
    for i, row in enumerate(cand_fields):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("Hybrid Screener Universe (Detail)")
    pdf.body_text(
        "The screener universe is constructed in pre-flight and passed to Agent 2 as a fixed list. "
        "Agent 2 CANNOT add tickers -- it can only select from what it receives."
    )
    pdf.info_box(
        "STATIC COMPONENT (60 tickers)",
        "Curated across 8 sectors: Tech/AI (15), Semiconductors (10), Fintech/Payments (8), "
        "Energy/Commodities (7), Healthcare/Biotech (6), Consumer/Retail (5), "
        "Industrials/Defense (5), REITs/Financials (4). See Section 10 for full list."
    )
    pdf.info_box(
        "DYNAMIC COMPONENT (Assembly Momentum)",
        "Sourced from Assembly Private momentum screens:\n"
        "  - Top Gainers: Stocks with unusual daily/weekly gains\n"
        "  - Breakout Setups: Technical breakout candidates\n"
        "  - Unusual Volume: Stocks with volume >2x 20d average\n"
        "Filters applied: >$5 price, >$100M market cap\n"
        "Tagged SOURCE='Assembly Momentum' for traceability"
    )

    pdf.sub_title("Deep Research Protocol (Detail)")
    pdf.body_text(
        "Agent 2 must follow a structured 5-step research process before outputting candidates. "
        "This is enforced via the research_scratchpad requirement."
    )
    pdf.bullet("Step 1 - Inventory: List all numerical data available for each potential candidate. "
               "P/E, Fwd P/E, PEG, margins, FCF, D/E, beta, volume.")
    pdf.bullet("Step 2 - Filters: Verify >$5 share price AND >$100M market cap. Eliminate failures.")
    pdf.bullet("Step 3 - Bear Case: For each surviving candidate, explicitly argue the downside. "
               "What could go wrong? Overvaluation? Sector headwinds? Earnings risk?")
    pdf.bullet("Step 4 - Score: Assign conviction 0-10 with explicit justification. Must reference "
               "at least 3 quantitative data points per score.")
    pdf.bullet("Step 5 - Theme Verification: Confirm THEME_MATCH is character-for-character identical "
               "to one of Agent 1's preferred_themes. If no theme matches, candidate is rejected.")
    pdf.ln(2)

    pdf.sub_title("Fundamental Data Available")
    pdf.body_text(
        "Agent 2 receives pre-fetched fundamental data for every ticker in the screener universe. "
        "This data is collected during pre-flight via yfinance and passed as structured JSON."
    )
    pdf.bullet("Valuation: P/E (TTM), Forward P/E, PEG Ratio, Price/Sales, Price/Book")
    pdf.bullet("Profitability: Gross Margin, Operating Margin, Net Margin, ROE, ROA")
    pdf.bullet("Growth: Revenue Growth (YoY), Earnings Growth (YoY), FCF Growth")
    pdf.bullet("Balance Sheet: Debt/Equity, Current Ratio, Cash/Share")
    pdf.bullet("Trading: Beta, Avg Volume (20d), Short Interest, Institutional Ownership")
    pdf.bullet("Technical: Current Price, 52w High/Low, Distance from MA50/MA200")
def build_agent3(pdf):
    """PAGE 13-14: Agent 3 - Smart Money Verifier"""
    pdf.add_page()
    pdf.section_title("6. AGENT 3: SMART MONEY VERIFIER")

    pdf.sub_title("Overview")
    pdf.body_text(
        "Agent 3 acts as a sentiment cross-check. For each candidate from Agent 2, it scores "
        "smart money X/Twitter sentiment over a 7-day lookback window using 15 curated accounts. "
        "This provides an independent verification layer before positions are sized."
    )

    pdf.sub_title("System Prompt (Verbatim)")
    prompt_text = (
        'You are Agent 3: The Smart Money Verifier.\n\n'
        'YOUR JOB: Score smart money X/Twitter sentiment for each candidate. 7-day lookback window.\n\n'
        'SCORING:\n'
        '9-10: Strong alignment -- multiple smart money accounts bullish, specific price targets\n'
        '7-8: Moderate alignment -- some positive mentions, general sector enthusiasm\n'
        '5-6: Neutral/silent -- no meaningful mentions either way\n'
        '3-4: Contested -- mixed signals, some bearish commentary\n'
        '1-2: Divergent -- smart money actively bearish or warning\n'
        '0: Crowded trade warning -- excessive bullish consensus (contrarian signal)\n\n'
        'Output JSON: agent, timestamp, verifications array (ticker, verification_score, '
        'sentiment_read, key_mentions, flag), overall_note'
    )
    pdf.code_block(prompt_text)

    pdf.sub_title("X API Integration")
    pdf.body_text(
        "Agent 3 consumes pre-fetched X API data from the pre-flight layer. The data is collected "
        "using the search/recent endpoint (v2 API) with a pay-per-use tier."
    )
    cols = ["Parameter", "Value"]
    widths = [60, 130]
    pdf.table_header(cols, widths)
    api_details = [
        ["Endpoint", "GET /2/tweets/search/recent"],
        ["API Version", "v2"],
        ["Tier", "Pay-per-use (Basic or Pro)"],
        ["Max Lookback", "7 days"],
        ["Query Format", "'$TICKER OR TICKER from:account1 OR from:account2'"],
        ["Tweet Fields", "created_at, text, public_metrics, author_id"],
        ["Max Results/Query", "100 (paginated if needed)"],
        ["Rate Limit (Basic)", "300 requests / 15 minutes"],
        ["Rate Limit (Pro)", "450 requests / 15 minutes"],
    ]
    for i, row in enumerate(api_details):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("15 Curated Smart Money Accounts")
    pdf.body_text(
        "These accounts were selected for their track record, influence, and signal-to-noise ratio "
        "in financial markets commentary. The list is reviewed quarterly."
    )
    cols2 = ["#", "Handle", "Focus Area"]
    widths2 = [10, 50, 130]
    pdf.table_header(cols2, widths2)
    accounts = [
        ["1", "@unusual_whales", "Options flow, unusual activity alerts"],
        ["2", "@DeItaone", "Breaking financial news, Fed/macro"],
        ["3", "@zaborolux", "Macro analysis, credit markets"],
        ["4", "@modaborealius", "Quantitative analysis, positioning data"],
        ["5", "@WallStJesus", "Technical analysis, momentum plays"],
        ["6", "@jimcramer", "Contrarian indicator, retail sentiment"],
        ["7", "@chaaborealius", "Macro, rates, commodities"],
        ["8", "@GurgavinS", "Tech sector, earnings analysis"],
        ["9", "@PelicanCap", "Short selling, forensic accounting"],
        ["10", "@BrianSozzi", "Consumer/retail sector, earnings"],
        ["11", "@StockMKTNewz", "Market news aggregation, real-time"],
        ["12", "@SamRo", "Economic data, labor market, macro"],
        ["13", "@TechFundament", "Tech fundamentals, SaaS metrics"],
        ["14", "@OptionsHawk", "Options flow analysis, smart money"],
        ["15", "@MacroAlf", "Global macro, cross-asset analysis"],
    ]
    for i, row in enumerate(accounts):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))

    pdf.add_page()
    pdf.sub_title("Scoring Framework (Detail)")
    pdf.body_text(
        "Agent 3 evaluates sentiment across multiple dimensions for each candidate:"
    )
    pdf.bullet("Volume: How many of the 15 accounts mentioned the ticker in 7 days?")
    pdf.bullet("Tone: Bullish, bearish, neutral, or analytical?")
    pdf.bullet("Specificity: Generic sector commentary vs specific price targets/catalysts?")
    pdf.bullet("Consensus: Do accounts agree or diverge?")
    pdf.bullet("Recency: More weight to recent mentions (last 2 days vs 5-7 days ago)")
    pdf.ln(2)

    pdf.sub_title("Output Contract")
    cols3 = ["Field", "Type", "Description"]
    widths3 = [50, 40, 100]
    pdf.table_header(cols3, widths3)
    outputs = [
        ["agent", "string", '"Agent 3: Smart Money Verifier"'],
        ["timestamp", "string (ISO)", "2025-05-19T07:00:00Z"],
        ["verifications", "array", "One per candidate from Agent 2"],
    ]
    for i, row in enumerate(outputs):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("Verification Object Schema")
    cols4 = ["Field", "Type", "Example"]
    widths4 = [45, 35, 110]
    pdf.table_header(cols4, widths4)
    ver_fields = [
        ["ticker", "string", "NVDA"],
        ["verification_score", "int (0-10)", "8"],
        ["sentiment_read", "string", "Moderate bullish alignment"],
        ["key_mentions", "string[]", '["@unusual_whales: call sweep"]'],
        ["flag", "string|null", "null (or 'CROWDED_TRADE')"],
    ]
    for i, row in enumerate(ver_fields):
        pdf.table_row(row, widths4, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("Special Flags")
    pdf.bullet("CROWDED_TRADE (score=0): >10 of 15 accounts bullish. Excessive consensus is a "
               "contrarian warning. Agent 4 applies CONTRARIAN_MOD if triggered.")
    pdf.bullet("NO_DATA: Fewer than 2 mentions found. Score defaults to 5 (neutral). Agent proceeds "
               "but notes low confidence in sentiment verification.")
    pdf.bullet("DIVERGENT: Smart money actively bearish while Agent 2 is bullish. Score 1-2. "
               "Strong headwind for the candidate.")
def build_agent4(pdf):
    """PAGE 15-17: Agent 4 - Risk Manager"""
    pdf.add_page()
    pdf.section_title("7. AGENT 4: RISK MANAGER")

    pdf.sub_title("Overview")
    pdf.body_text(
        "Agent 4 is split into two sub-agents: 4A (Stop Anchor Identifier, LLM-based) and "
        "4B (Risk Sizer, deterministic Python). Together they determine where to place stops "
        "and how large each position should be, respecting the risk budget."
    )

    pdf.sub_title("Agent 4A: Stop Anchor Identifier")
    pdf.body_text(
        "Agent 4A is an LLM agent (Claude Sonnet) that identifies the optimal stop-loss level "
        "for each candidate using technical support levels."
    )

    pdf.sub_title("Agent 4A System Prompt (Verbatim)")
    prompt_4a = (
        'You are Agent 4A: The Stop Anchor Identifier.\n\n'
        'YOUR JOB: Identify stop-loss levels from MA10, MA20, MA50, recent 20d low. '
        'Calculate FINAL_CONVICTION = avg(Agent 2, Agent 3 scores).\n\n'
        'Output JSON: agent, timestamp, stop_anchors array (ticker, prior_close, '
        'stop_anchor_price, stop_anchor_label, stop_distance_pct, final_conviction, reasoning)'
    )
    pdf.code_block(prompt_4a)

    pdf.sub_title("Stop Anchor Selection Logic")
    pdf.body_text(
        "Agent 4A evaluates four technical levels for each candidate and selects the most "
        "appropriate stop anchor:"
    )
    cols = ["Level", "Calculation", "When Preferred"]
    widths = [35, 55, 100]
    pdf.table_header(cols, widths)
    levels = [
        ["MA10", "10-day moving avg", "Tight stop for momentum trades"],
        ["MA20", "20-day moving avg", "Standard stop for swing trades"],
        ["MA50", "50-day moving avg", "Wider stop for position trades"],
        ["20d Low", "Lowest close in 20d", "Maximum stop distance anchor"],
    ]
    for i, row in enumerate(levels):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.body_text(
        "Selection criteria: The stop must be within 10% of current price (hard constraint). "
        "Among valid anchors, Agent 4A selects based on regime -- tighter stops in RISK-OFF, "
        "wider stops in RISK-ON. The stop_distance_pct is calculated as: "
        "(prior_close - stop_anchor_price) / prior_close * 100."
    )

    pdf.sub_title("FINAL_CONVICTION Calculation")
    pdf.info_box(
        "Formula",
        "FINAL_CONVICTION = (Agent_2_conviction + Agent_3_verification) / 2\n\n"
        "Example: Agent 2 scores NVDA at 8, Agent 3 scores at 7\n"
        "FINAL_CONVICTION = (8 + 7) / 2 = 7.5 (rounded to 8 for modifier lookup)"
    )

    pdf.sub_title("Agent 4A Output Contract")
    cols2 = ["Field", "Type", "Example"]
    widths2 = [50, 40, 100]
    pdf.table_header(cols2, widths2)
    outputs_4a = [
        ["ticker", "string", "NVDA"],
        ["prior_close", "float", "924.50"],
        ["stop_anchor_price", "float", "892.30"],
        ["stop_anchor_label", "string", "MA20"],
        ["stop_distance_pct", "float", "3.48"],
        ["final_conviction", "int", "8"],
        ["reasoning", "string", "MA20 provides clean support..."],
    ]
    for i, row in enumerate(outputs_4a):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))

    # Agent 4B on new page
    pdf.add_page()
    pdf.sub_title("Agent 4B: Risk Sizer (Deterministic Python)")
    pdf.body_text(
        "Agent 4B is NOT an LLM -- it is a deterministic Python function that applies a "
        "multiplicative sizing formula. There is zero AI judgment here; it is pure math."
    )

    pdf.sub_title("Multiplicative Sizing Formula")
    pdf.info_box(
        "CORE FORMULA",
        "Position = BASE_ALLOC x CONVICTION_MOD x VOL_MOD x POSTURE_MOD x CONTRARIAN_MOD"
    )
    pdf.ln(2)

    pdf.sub_title("BASE_ALLOC")
    pdf.body_text("Fixed at 15% of account = $1,500 per position (on a $10,000 account).")
    pdf.ln(1)

    pdf.sub_title("CONVICTION_MOD")
    cols3 = ["Final Conviction", "Modifier"]
    widths3 = [95, 95]
    pdf.table_header(cols3, widths3)
    conv_rows = [
        ["5", "0.60"],
        ["6", "0.76"],
        ["7", "0.88"],
        ["8", "1.00"],
        ["9", "1.20"],
        ["10", "1.40"],
    ]
    for i, row in enumerate(conv_rows):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("VOL_MOD")
    cols4 = ["Vol Regime", "Modifier", "Rationale"]
    widths4 = [45, 35, 110]
    pdf.table_header(cols4, widths4)
    vol_rows = [
        ["COMPRESSED", "1.20", "Low vol = opportunity for larger positions"],
        ["NORMAL", "1.00", "Standard sizing"],
        ["ELEVATED", "0.70", "Reduce exposure in choppy markets"],
        ["STRESSED", "0.40", "Minimal sizing in high-stress environments"],
    ]
    for i, row in enumerate(vol_rows):
        pdf.table_row(row, widths4, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("POSTURE_MOD")
    cols5 = ["Posture", "Modifier", "Regime"]
    widths5 = [45, 35, 110]
    pdf.table_header(cols5, widths5)
    pos_rows = [
        ["Aggressive", "1.00", "RISK-ON"],
        ["Offensive", "0.85", "CAUTIOUS RISK-ON"],
        ["Defensive", "0.60", "RISK-OFF"],
        ["Bunker", "0.30", "CRISIS"],
    ]
    for i, row in enumerate(pos_rows):
        pdf.table_row(row, widths5, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("CONTRARIAN_MOD")
    pdf.body_text(
        "Default: 1.0 (no adjustment). If Agent 3 flags CROWDED_TRADE for a ticker, "
        "CONTRARIAN_MOD = 0.5, halving the position size as a risk reduction measure."
    )
    pdf.ln(2)

    pdf.sub_title("Sizing Example")
    pdf.code_block(
        "Scenario: CAUTIOUS RISK-ON, NORMAL vol, NVDA conviction 8, no crowded trade\n\n"
        "Position = $1,500 x 1.00 x 1.00 x 0.85 x 1.0\n"
        "Position = $1,275\n\n"
        "At NVDA price $924.50:\n"
        "Shares = floor($1,275 / $924.50) = 1 share\n"
        "Actual position = $924.50\n"
        "Stop at MA20 ($892.30) = $32.20 risk per share\n"
        "Total risk = $32.20 (within $150/trade limit)"
    )

    # Risk budget page
    pdf.add_page()
    pdf.sub_title("Risk Budget Constraints")
    pdf.info_box(
        "HARD LIMITS (NON-NEGOTIABLE)",
        "- Maximum risk per SESSION: $500\n"
        "- Maximum risk per TRADE: $150\n"
        "- All stops must be within 10% of entry price\n"
        "- If calculated risk exceeds limits, position is reduced until compliant\n"
        "- If no compliant size exists, trade is REJECTED"
    )
    pdf.ln(2)

    pdf.sub_title("Risk Calculation")
    pdf.body_text(
        "Risk per trade = shares x (entry_price - stop_price)\n\n"
        "If risk > $150: reduce shares until risk <= $150\n"
        "If risk > $500 cumulative for session: reject additional trades\n"
        "If stop_distance > 10%: reject trade (stop too wide)"
    )
    pdf.ln(2)

    pdf.sub_title("Tear Sheet Format")
    pdf.body_text(
        "Agent 4B outputs a tear sheet for each approved trade. This is the final deliverable "
        "that contains all information needed for execution."
    )
    pdf.code_block(
        "TEAR SHEET -- NVDA\n"
        "=================================\n"
        "Regime: CAUTIOUS RISK-ON | Vol: NORMAL | Posture: Offensive\n"
        "Conviction: Agent2=8, Agent3=7, Final=8\n"
        "Theme: AI Infrastructure\n"
        "Source: Screener Stage 2\n"
        "---------------------------------\n"
        "Entry: $924.50 (prior close)\n"
        "Stop: $892.30 (MA20) -- 3.48% distance\n"
        "Position Size: $924.50 (1 share)\n"
        "Risk: $32.20 (2.15% of session budget)\n"
        "---------------------------------\n"
        "Sizing Math:\n"
        "  BASE: $1,500 (15%)\n"
        "  x CONVICTION_MOD: 1.00 (score 8)\n"
        "  x VOL_MOD: 1.00 (NORMAL)\n"
        "  x POSTURE_MOD: 0.85 (Offensive)\n"
        "  x CONTRARIAN_MOD: 1.00\n"
        "  = $1,275 -> 1 share @ $924.50\n"
        "---------------------------------\n"
        "Thesis: [from Agent 2]\n"
        "Catalyst: [from Agent 2]\n"
        "Smart Money: [from Agent 3]\n"
        "================================="
    )
def build_agent5(pdf):
    """PAGE 18-19: Agent 5 - Position Monitor"""
    pdf.add_page()
    pdf.section_title("8. AGENT 5: POSITION MONITOR")

    pdf.sub_title("Overview")
    pdf.body_text(
        "Agent 5 runs at 3:30 PM ET using a 3:25 PM price snapshot. It reviews all open positions "
        "and makes HOLD, TRIM, or CLOSE decisions based on trailing stop rules, daily P&L, and "
        "macro conditions. It is the last line of defense for risk management."
    )

    pdf.sub_title("System Prompt (Verbatim)")
    prompt_text = (
        'You are Agent 5: The Position Monitor.\n\n'
        'YOUR JOB: At 3:30 PM ET, review positions using 3:25 PM snapshot. HOLD, TRIM, or CLOSE.\n\n'
        'TRAILING STOP RULES:\n'
        '- Up >2%: tighten to breakeven\n'
        '- Up >5%: trail to 50% of gains\n'
        '- Up >10%: trail to 75% of gains\n'
        '- Never widen a stop\n\n'
        'END-OF-DAY:\n'
        '- <1% gain today: consider closing\n'
        '- Down >5%: strongly consider closing\n'
        '- VIX spike >20%: tighten all stops\n\n'
        'Output JSON: agent, timestamp, decisions array, portfolio_summary'
    )
    pdf.code_block(prompt_text)

    pdf.sub_title("Trailing Stop Rules (Detail)")
    cols = ["Condition", "Action", "Example"]
    widths = [45, 55, 90]
    pdf.table_header(cols, widths)
    rules = [
        ["Up >2% from entry", "Tighten stop to breakeven", "Entry $100, now $102, stop -> $100"],
        ["Up >5% from entry", "Trail to 50% of gains", "Entry $100, now $105, stop -> $102.50"],
        ["Up >10% from entry", "Trail to 75% of gains", "Entry $100, now $110, stop -> $107.50"],
        ["Never widen a stop", "One-way ratchet only", "Stop can only move UP, never down"],
    ]
    for i, row in enumerate(rules):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("End-of-Day Decision Framework")
    cols2 = ["Condition", "Action", "Rationale"]
    widths2 = [50, 45, 95]
    pdf.table_header(cols2, widths2)
    eod = [
        ["<1% gain today", "Consider CLOSE", "Weak momentum, opportunity cost"],
        ["Down >5% today", "Strongly consider CLOSE", "Significant loss, cut exposure"],
        ["VIX spike >20%", "Tighten ALL stops", "Regime shift risk, protect gains"],
        ["At stop level", "CLOSE (mandatory)", "Stop hit = automatic exit"],
        ["Strong momentum", "HOLD", "Let winners run with trail"],
    ]
    for i, row in enumerate(eod):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Input Contract")
    cols3 = ["Field", "Source", "Description"]
    widths3 = [50, 50, 90]
    pdf.table_header(cols3, widths3)
    inputs = [
        ["open_positions", "Portfolio state", "All current holdings"],
        ["price_snapshot", "yfinance (3:25 PM)", "Current prices per ticker"],
        ["entry_prices", "Trade log", "Original entry price per position"],
        ["current_stops", "Trade log", "Current stop level per position"],
        ["daily_pnl", "Calculated", "Intraday P&L per position"],
        ["vix_current", "yfinance", "Current VIX level"],
        ["vix_change_pct", "Calculated", "VIX change from open"],
    ]
    for i, row in enumerate(inputs):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))

    pdf.add_page()
    pdf.sub_title("Output Contract")
    cols4 = ["Field", "Type", "Description"]
    widths4 = [50, 40, 100]
    pdf.table_header(cols4, widths4)
    outputs = [
        ["agent", "string", '"Agent 5: Position Monitor"'],
        ["timestamp", "string (ISO)", "2025-05-19T15:30:00Z"],
        ["decisions", "array", "One per open position"],
        ["portfolio_summary", "object", "Aggregate P&L and risk status"],
    ]
    for i, row in enumerate(outputs):
        pdf.table_row(row, widths4, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("Decision Object Schema")
    cols5 = ["Field", "Type", "Example"]
    widths5 = [45, 35, 110]
    pdf.table_header(cols5, widths5)
    dec_fields = [
        ["ticker", "string", "NVDA"],
        ["action", "string (enum)", "HOLD | TRIM | CLOSE"],
        ["current_price", "float", "930.20"],
        ["entry_price", "float", "924.50"],
        ["unrealized_pnl", "float", "+5.70"],
        ["unrealized_pct", "float", "+0.62%"],
        ["old_stop", "float", "892.30"],
        ["new_stop", "float", "924.50 (breakeven)"],
        ["reasoning", "string", "Up 0.62%, tighten to BE"],
    ]
    for i, row in enumerate(dec_fields):
        pdf.table_row(row, widths5, fill=(i % 2 == 0))
    pdf.ln(2)

    pdf.sub_title("Portfolio Summary Schema")
    pdf.code_block(
        "portfolio_summary: {\n"
        "  total_positions: 2,\n"
        "  total_exposure: $1,849.00,\n"
        "  total_unrealized_pnl: +$12.40,\n"
        "  total_unrealized_pct: +0.67%,\n"
        "  session_risk_used: $64.40 / $500.00,\n"
        "  vix_status: 'VIX 16.2, +1.3% from open -- normal',\n"
        "  recommendation: 'Portfolio healthy. All stops tightened.'\n"
        "}"
    )
def build_engineering(pdf):
    """PAGE 20-21: Engineering Implementation"""
    pdf.add_page()
    pdf.section_title("9. ENGINEERING IMPLEMENTATION")

    pdf.sub_title("File Structure")
    pdf.code_block(
        "trading-pipeline/\n"
        "  orchestrator.py           -- Main pipeline runner\n"
        "  config.py                 -- Constants, API keys, schedule\n"
        "  preflight/\n"
        "    data_collector.py       -- yfinance + Assembly + X API\n"
        "    assembly_scraper.py     -- Browser-based Assembly Private scraper\n"
        "    x_api_client.py         -- X API search/recent wrapper\n"
        "    screener_builder.py     -- Hybrid universe construction\n"
        "    fundamental_fetch.py    -- yfinance fundamental data fetch\n"
        "  agents/\n"
        "    agent1_macro.py         -- Macro Director (Claude Sonnet)\n"
        "    agent2_screener.py      -- Fundamental Screener (Gemini 3.1 Pro)\n"
        "    agent3_sentiment.py     -- Smart Money Verifier (Claude Sonnet)\n"
        "    agent4a_stops.py        -- Stop Anchor Identifier (Claude Sonnet)\n"
        "    agent4b_sizer.py        -- Risk Sizer (deterministic Python)\n"
        "    agent5_monitor.py       -- Position Monitor (Claude Sonnet)\n"
        "  output/\n"
        "    macro_data.json         -- Pre-flight macro data\n"
        "    assembly_data.json      -- Assembly Private extract\n"
        "    x_sentiment_raw.json    -- X API raw tweet data\n"
        "    screener_universe.json  -- Merged ticker list\n"
        "    technical_data.json     -- MAs and technical levels\n"
        "    agent1_output.json      -- Macro Director output\n"
        "    agent2_output.json      -- Screener output\n"
        "    agent3_output.json      -- Sentiment output\n"
        "    agent4_output.json      -- Risk Manager output\n"
        "    agent5_output.json      -- Monitor output\n"
        "    tear_sheets/            -- Per-trade tear sheet PDFs\n"
        "    logs/                   -- Pipeline execution logs"
    )
    pdf.ln(2)

    pdf.sub_title("APIs Used")
    cols = ["API", "Provider", "Usage", "Auth"]
    widths = [40, 40, 60, 50]
    pdf.table_header(cols, widths)
    apis = [
        ["Anthropic", "Claude Sonnet", "Agents 1,3,4A,5", "API key (env)"],
        ["Google GenAI", "Gemini 3.1 Pro", "Agent 2 (deep res)", "API key (env)"],
        ["X API v2", "Twitter/X", "Sentiment data", "Bearer token"],
        ["yfinance", "Yahoo Finance", "Market data, fundmtls", "None (free)"],
        ["Assembly", "assemblyprivate", "Institutional data", "Browser session"],
    ]
    for i, row in enumerate(apis):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Assembly Private Scraping Method")
    pdf.body_text(
        "Assembly Private (assemblyprivate.com) is a single-page application (SPA) that requires "
        "JavaScript rendering for data extraction. The scraping approach:"
    )
    pdf.bullet("Browser: Headless Chromium via Playwright")
    pdf.bullet("Auth: Session cookie from authenticated browser profile")
    pdf.bullet("Navigation: Direct URL access to specific data panels")
    pdf.bullet("Extraction: DOM queries on rendered SPA elements")
    pdf.bullet("Parsing: Structured extraction into typed JSON objects")
    pdf.bullet("Error handling: Graceful degradation if Assembly is down (pipeline continues)")
    pdf.bullet("Rate limiting: Single scrape per run, no rapid polling")
    pdf.ln(2)

    pdf.sub_title("Orchestrator Flow")
    pdf.body_text(
        "The orchestrator (orchestrator.py) is the main entry point. It runs the pipeline "
        "sequentially, passing outputs from each stage to the next."
    )
    pdf.code_block(
        "def run_pipeline():\n"
        "    # Phase 1: Pre-Flight (6:00 AM)\n"
        "    macro_data = collect_macro_data()        # yfinance\n"
        "    assembly_data = scrape_assembly()         # Browser\n"
        "    universe = build_screener_universe()      # Static + Assembly\n"
        "    fundamentals = fetch_fundamentals(universe)# yfinance\n"
        "    technicals = fetch_technicals(universe)   # yfinance\n"
        "    x_data = fetch_x_sentiment(universe)      # X API\n"
        "\n"
        "    # Phase 2: Agent Chain (6:15 AM - 7:30 AM)\n"
        "    a1_out = run_agent1(macro_data, assembly_data)\n"
        "    if a1_out['regime'] == 'DEFER':\n"
        "        log('DEFER regime -- pipeline halted')\n"
        "        return\n"
        "\n"
        "    a2_out = run_agent2(a1_out, universe, fundamentals)\n"
        "    if not a2_out['candidates']:\n"
        "        log('No candidates -- pipeline complete')\n"
        "        return\n"
        "\n"
        "    a3_out = run_agent3(a2_out['candidates'], x_data)\n"
        "    a4_out = run_agent4(a1_out, a2_out, a3_out, technicals)\n"
        "    generate_tear_sheets(a4_out)\n"
        "\n"
        "    # Phase 3: Monitor (3:30 PM)\n"
        "    # Scheduled separately via cron\n"
        "    # run_agent5(open_positions, price_snapshot)"
    )

    pdf.add_page()
    pdf.sub_title("Output Files (Detail)")
    pdf.body_text(
        "Each agent persists its output as a JSON file in the output/ directory. Files are "
        "timestamped and versioned for audit trail purposes."
    )
    pdf.bullet("Naming: agent{N}_output_{YYYYMMDD_HHMMSS}.json")
    pdf.bullet("Retention: 30 days of historical outputs")
    pdf.bullet("Format: Pretty-printed JSON with ISO 8601 timestamps")
    pdf.bullet("Validation: JSON schema validation before persistence")
    pdf.ln(2)

    pdf.sub_title("Error Handling Strategy")
    pdf.bullet("API failures: Retry with exponential backoff (3 attempts, 2s/4s/8s)")
    pdf.bullet("Assembly down: Skip Assembly data, proceed with yfinance-only macro")
    pdf.bullet("X API quota: Graceful degradation, Agent 3 scores default to 5 (neutral)")
    pdf.bullet("Agent timeout: 120s per agent, kill and log on timeout")
    pdf.bullet("Invalid output: JSON schema validation, reject and retry once")
    pdf.bullet("Kill-switch: MOVE/Credit unavailable = DEFER, full pipeline halt")
    pdf.ln(2)

    pdf.sub_title("Logging")
    pdf.bullet("Level: INFO for normal flow, WARN for degraded, ERROR for failures")
    pdf.bullet("Format: ISO timestamp | agent | level | message")
    pdf.bullet("Destination: output/logs/pipeline_{YYYYMMDD}.log")
    pdf.bullet("Rotation: Daily rotation, 30-day retention")
def build_screener_universe(pdf):
    """PAGE 22: Screener Universe"""
    pdf.add_page()
    pdf.section_title("10. SCREENER UNIVERSE")

    pdf.sub_title("Static Universe (60 Tickers)")
    pdf.body_text(
        "The static universe is curated across 8 sectors. These tickers are included in every "
        "pipeline run regardless of Assembly data availability."
    )

    # Tech/AI
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Tech / AI (15 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "MSFT, AAPL, GOOGL, META, AMZN, NVDA, CRM, NOW, SNOW, PLTR, "
        "AI, PATH, DDOG, NET, CRWD"
    )
    pdf.ln(2)

    # Semiconductors
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Semiconductors (10 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "AMD, AVGO, QCOM, MRVL, TSM, ASML, LRCX, AMAT, KLAC, MU"
    )
    pdf.ln(2)

    # Fintech
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Fintech / Payments (8 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "V, MA, SQ, PYPL, COIN, AFRM, SOFI, NU"
    )
    pdf.ln(2)

    # Energy
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Energy / Commodities (7 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "XOM, CVX, OXY, SLB, FSLR, ENPH, LNG"
    )
    pdf.ln(2)

    # Healthcare
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Healthcare / Biotech (6 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "LLY, UNH, ABBV, ISRG, DXCM, MRNA"
    )
    pdf.ln(2)

    # Consumer
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Consumer / Retail (5 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "COST, TGT, LULU, NKE, SBUX"
    )
    pdf.ln(2)

    # Industrials
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "Industrials / Defense (5 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "LMT, RTX, GD, CAT, DE"
    )
    pdf.ln(2)

    # REITs
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 6, "REITs / Financials (4 tickers)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK_GRAY)
    pdf.multi_cell(0, 5,
        "O, AMT, JPM, GS"
    )
    pdf.ln(4)

    pdf.sub_title("Assembly Dynamic Tickers")
    pdf.body_text(
        "Dynamic tickers are sourced from Assembly Private momentum screens during pre-flight. "
        "They change daily based on market conditions."
    )
    pdf.bullet("Source: Assembly Private momentum screens (top gainers, breakouts, unusual volume)")
    pdf.bullet("Filters: >$5 share price, >$100M market cap (same as static universe)")
    pdf.bullet("Tagging: SOURCE='Assembly Momentum' to distinguish from static tickers")
    pdf.bullet("Deduplication: If an Assembly ticker already exists in static universe, it is not duplicated")
    pdf.bullet("Typical count: 5-15 additional tickers per day (varies with market activity)")
    pdf.bullet("Fallback: If Assembly is unavailable, pipeline runs with 60 static tickers only")
def build_quick_reference(pdf):
    """PAGE 23: Quick Reference"""
    pdf.add_page()
    pdf.section_title("11. QUICK REFERENCE")

    pdf.sub_title("Key Constants")
    cols = ["Constant", "Value", "Used By"]
    widths = [60, 50, 80]
    pdf.table_header(cols, widths)
    constants = [
        ["ACCOUNT_SIZE", "$10,000", "Agent 4B"],
        ["BASE_ALLOC_PCT", "15%", "Agent 4B"],
        ["BASE_ALLOC_USD", "$1,500", "Agent 4B"],
        ["MAX_RISK_SESSION", "$500", "Agent 4B"],
        ["MAX_RISK_TRADE", "$150", "Agent 4B"],
        ["MAX_STOP_DISTANCE", "10%", "Agent 4A, 4B"],
        ["MAX_CANDIDATES", "3", "Agent 2"],
        ["X_LOOKBACK_DAYS", "7", "Agent 3"],
        ["MONITOR_TIME", "3:30 PM ET", "Agent 5"],
        ["SNAPSHOT_TIME", "3:25 PM ET", "Agent 5"],
        ["STATIC_UNIVERSE_SIZE", "60 tickers", "Pre-flight"],
    ]
    for i, row in enumerate(constants):
        pdf.table_row(row, widths, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("Daily Schedule")
    cols2 = ["Time (ET)", "Component", "Duration"]
    widths2 = [40, 100, 50]
    pdf.table_header(cols2, widths2)
    schedule = [
        ["6:00 AM", "Pre-flight data collection", "~15 min"],
        ["6:15 AM", "Agent 1: Macro Director", "~2 min"],
        ["6:30 AM", "Agent 2: Fundamental Screener", "~20 min"],
        ["7:00 AM", "Agent 3: Smart Money Verifier", "~10 min"],
        ["7:15 AM", "Agent 4: Risk Manager (4A + 4B)", "~5 min"],
        ["7:30 AM", "Tear Sheet Generation", "~1 min"],
        ["3:30 PM", "Agent 5: Position Monitor", "~3 min"],
    ]
    for i, row in enumerate(schedule):
        pdf.table_row(row, widths2, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("Risk Limits Summary")
    cols3 = ["Limit", "Value", "Enforcement"]
    widths3 = [55, 45, 90]
    pdf.table_header(cols3, widths3)
    limits = [
        ["Per-trade risk", "$150 max", "Agent 4B (hard reject)"],
        ["Per-session risk", "$500 max", "Agent 4B (cumulative)"],
        ["Stop distance", "<= 10%", "Agent 4A (hard reject)"],
        ["Position size", "<= 20% of account", "Agent 4B (cap)"],
        ["Min conviction", "Regime-dependent", "Agent 2 (floor)"],
        ["Min price", ">$5", "Pre-flight filter"],
        ["Min market cap", ">$100M", "Pre-flight filter"],
    ]
    for i, row in enumerate(limits):
        pdf.table_row(row, widths3, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("API Endpoints")
    cols4 = ["Service", "Endpoint"]
    widths4 = [50, 140]
    pdf.table_header(cols4, widths4)
    endpoints = [
        ["Anthropic", "https://api.anthropic.com/v1/messages"],
        ["Google GenAI", "https://generativelanguage.googleapis.com/v1"],
        ["X API", "https://api.twitter.com/2/tweets/search/recent"],
        ["yfinance", "Python library (no REST endpoint)"],
        ["Assembly", "https://app.assemblyprivate.com (browser)"],
    ]
    for i, row in enumerate(endpoints):
        pdf.table_row(row, widths4, fill=(i % 2 == 0))
    pdf.ln(4)

    pdf.sub_title("Conviction Modifier Quick Lookup")
    cols5 = ["Score", "5", "6", "7", "8", "9", "10"]
    widths5 = [40, 25, 25, 25, 25, 25, 25]
    pdf.table_header(cols5, widths5)
    pdf.table_row(["Modifier", "0.60", "0.76", "0.88", "1.00", "1.20", "1.40"], widths5, fill=True)
    pdf.ln(4)

    pdf.sub_title("Regime -> Posture Quick Lookup")
    cols6 = ["Regime", "Posture", "Floor", "Posture Mod"]
    widths6 = [50, 45, 35, 60]
    pdf.table_header(cols6, widths6)
    regimes = [
        ["RISK-ON", "Aggressive", "5", "1.00"],
        ["CAUTIOUS RISK-ON", "Offensive", "6", "0.85"],
        ["RISK-OFF", "Defensive", "7", "0.60"],
        ["CRISIS", "Bunker", "9", "0.30"],
        ["DEFER", "Hold", "10", "N/A (no trades)"],
    ]
    for i, row in enumerate(regimes):
        pdf.table_row(row, widths6, fill=(i % 2 == 0))
    pdf.ln(6)

    # Document footer
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MED_GRAY)
    pdf.cell(0, 5, "-- End of Document --", align="C", ln=True)
    pdf.cell(0, 5, "Open Claw Trading Pipeline v3 | OCPlatform | Chris Buetti", align="C", ln=True)
def main():
    pdf = OCPlatformDoc()
    build_cover(pdf)
    build_toc(pdf)
    build_overview(pdf)
    build_v3_changes(pdf)
    build_preflight(pdf)
    build_agent1(pdf)
    build_agent2(pdf)
    build_agent3(pdf)
    build_agent4(pdf)
    build_agent5(pdf)
    build_engineering(pdf)
    build_screener_universe(pdf)
    build_quick_reference(pdf)

    pdf.output(OUTPUT_PDF)
    print(f"PDF generated: {OUTPUT_PDF}")
    print(f"Total pages: {pdf.page_no()}")


if __name__ == "__main__":
    main()
