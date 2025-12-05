import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
import altair as alt
import calendar
import os
import textwrap


def _normalize_hex(hex_color: str) -> str:
    """Return a safe 6-character hex color prefixed with #."""
    if not isinstance(hex_color, str):
        return "#0b1220"
    value = hex_color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return "#0b1220"
    try:
        int(value, 16)
    except ValueError:
        return "#0b1220"
    return f"#{value.lower()}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    normalized = _normalize_hex(hex_color)[1:]
    return tuple(int(normalized[i : i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def build_theme_from_background(bg_hex: str) -> dict:
    """Return derived theme colors ensuring readable text on the chosen background."""
    normalized = _normalize_hex(bg_hex)
    luminance = _relative_luminance(_hex_to_rgb(normalized))
    is_light = luminance > 0.6
    if is_light:
        return {
            "bg_color": normalized,
            "text_primary": "#0f172a",
            "text_secondary": "#1e293b",
            "text_muted": "#475569",
            "chip_bg": "rgba(15, 23, 42, 0.08)",
            "chip_text": "#0f172a",
            "card_bg": "#ffffff",
            "card_border": "rgba(15, 23, 42, 0.08)",
            "card_text": "#0f172a",
            "card_muted": "#475569",
            "card_secondary": "#64748b",
            "card_soft": "rgba(15, 23, 42, 0.06)",
            "progress_track": "rgba(15, 23, 42, 0.08)",
        }
    return {
        "bg_color": normalized,
        "text_primary": "#f8fafc",
        "text_secondary": "rgba(248, 250, 252, 0.92)",
        "text_muted": "rgba(248, 250, 252, 0.75)",
        "chip_bg": "rgba(248, 250, 252, 0.2)",
        "chip_text": "#f8fafc",
        "card_bg": "rgba(15, 23, 42, 0.65)",
        "card_border": "rgba(248, 250, 252, 0.15)",
        "card_text": "#f8fafc",
        "card_muted": "rgba(248, 250, 252, 0.85)",
        "card_secondary": "rgba(248, 250, 252, 0.72)",
        "card_soft": "rgba(248, 250, 252, 0.18)",
        "progress_track": "rgba(248, 250, 252, 0.35)",
    }

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    _statsmodels_import_error = None
except ImportError as exc:
    ExponentialSmoothing = None
    _statsmodels_import_error = exc

st.set_page_config(page_title="Aghzia", layout="wide")

if "app_bg_color" not in st.session_state:
    st.session_state["app_bg_color"] = "#0b1220"

st.sidebar.color_picker(
    "App background",
    value=st.session_state["app_bg_color"],
    key="app_bg_color_picker",
)
if st.session_state["app_bg_color_picker"] != st.session_state["app_bg_color"]:
    st.session_state["app_bg_color"] = st.session_state["app_bg_color_picker"]
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

theme = build_theme_from_background(st.session_state["app_bg_color"])

style_template = textwrap.dedent(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
        :root {{
            --surface-soft: {bg_color};
            --text-primary: {text_primary};
            --text-secondary: {text_secondary};
            --text-muted: {text_muted};
            --chip-bg: {chip_bg};
            --chip-text: {chip_text};
            --card-bg: {card_bg};
            --card-border: {card_border};
            --card-text: {card_text};
            --card-muted: {card_muted};
            --card-secondary: {card_secondary};
            --card-soft: {card_soft};
            --progress-track: {progress_track};
        }}
        html, body, [data-testid="stAppViewContainer"], .main {{
            background: var(--surface-soft);
            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            color: var(--text-primary);
        }}
        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1300px;
        }}
        @media (max-width: 768px) {{
            .block-container {{
                padding: 0.75rem 0.65rem 2.5rem;
            }}
            section[data-testid="stSidebar"] {{
                width: 100% !important;
                border-radius: 20px;
                margin-bottom: 1rem;
            }}
            section[data-testid="stSidebar"] > div {{
                max-width: none !important;
                padding-bottom: 1rem;
            }}
        }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #071b35, #0c284f);
            color: #f8fafc;
            border-radius: 28px;
            padding-top: 0.5rem;
        }}
        section[data-testid="stSidebar"] * {{
            color: inherit !important;
        }}
        section[data-testid="stSidebar"] .css-1p5uq2i {{
            color: #f8fafc !important;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.75rem;
            width: 100%;
        }}
        @media (max-width: 768px) {{
            .kpi-grid {{
                grid-template-columns: 1fr;
                gap: 0.6rem;
            }}
        }}
        .kpi-card {{
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            box-shadow: none;
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            width: 100%;
            color: var(--card-text);
        }}
        .stat-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
        }}
        .stat-group {{
            display: flex;
            align-items: center;
            gap: 0.55rem;
        }}
        .stat-icon {{
            width: 36px;
            height: 36px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            background: var(--card-soft);
            color: var(--card-text);
        }}
        .stat-label {{
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            color: var(--text-muted);
        }}
        .stat-chip {{
            padding: 0.15rem 0.65rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            background: var(--chip-bg);
            color: var(--chip-text);
        }}
        .stat-value {{
            font-size: 2.05rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.1;
        }}
        .stat-secondary {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
        }}
        .stat-progress {{
            height: 6px;
            width: 100%;
            border-radius: 999px;
            background: var(--progress-track);
            overflow: hidden;
        }}
        .stat-progress-bar {{
            height: 100%;
            width: var(--progress, 100%);
            background: var(--accent, var(--text-primary));
            border-radius: inherit;
            transition: width 0.4s ease;
        }}
        @media (max-width: 480px) {{
            .kpi-card {{
                padding: 0.95rem 1rem;
            }}
        }}
        .mobile-stack > div {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        @media (max-width: 768px) {{
            .stRadio > div {{
                flex-direction: column !important;
                alignments: flex-start !important;
                gap: 0.35rem !important;
            }}
        }}
        .filter-chip {{
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.75rem;
            border-radius: 999px;
            background: var(--chip-bg);
            color: var(--chip-text);
            font-size: 0.8rem;
            margin: 0 0.25rem 0.3rem 0;
        }}
    </style>
    """
)

st.markdown(style_template.format(**theme), unsafe_allow_html=True)

st.title("BI.Commercial 💵")
st.markdown(
    "<span style='display:block;margin-top:-20px;'>Turn The decision UP 🚀</span>",
    unsafe_allow_html=True,
)
kpi_container = st.container()

st.sidebar.markdown("### Data Source")
uploaded_file = st.sidebar.file_uploader("Upload SQLite DB", type=["db", "sqlite", "sqlite3"])

TEMP_DB_PATH = "temp.db"

if uploaded_file:
    st.session_state["db_bytes"] = uploaded_file.getvalue()
    st.session_state["db_name"] = uploaded_file.name
    with open(TEMP_DB_PATH, "wb") as f:
        f.write(st.session_state["db_bytes"])
elif "db_bytes" not in st.session_state and os.path.exists(TEMP_DB_PATH):
    with open(TEMP_DB_PATH, "rb") as f:
        st.session_state["db_bytes"] = f.read()
    st.session_state.setdefault("db_name", os.path.basename(TEMP_DB_PATH))

if "db_bytes" not in st.session_state:
    st.sidebar.info("Please upload a SQLite database to get started.")
    st.stop()

file_conn = sqlite3.connect(TEMP_DB_PATH)

# Read tables
try:
    processed = pd.read_sql_query("SELECT * FROM processed_data", file_conn)
    master = pd.read_sql_query("SELECT * FROM FGData", file_conn)
except Exception as e:
    st.error(f"Error reading required tables: {e}")
    st.stop()

st.sidebar.success(f"DB Loaded Successfully ({st.session_state.get('db_name', 'temp.db')})")

# Merge with flexible column detection (master uses ItemNumber, processed uses item_code)
master_item_col = next((c for c in master.columns if c.lower() == "itemnumber"), None)
processed_item_col = next((c for c in processed.columns if c.lower() in {"item_code", "itemnumber", "itemcode"}), None)

if processed_item_col and master_item_col:
    merged = processed.merge(master, left_on=processed_item_col, right_on=master_item_col, how="left")
else:
    st.error(
        "Columns for linking not found. processed_data columns: "
        f"{processed.columns.tolist()} | FGData columns: {master.columns.tolist()}"
    )
    st.stop()

# Prepare date column if available
date_col_name = next((c for c in merged.columns if c.lower() == 'date'), None)
has_date_column = date_col_name is not None
if has_date_column:
    merged['_date_dt'] = pd.to_datetime(merged[date_col_name], errors='coerce')

# Sidebar filters
st.sidebar.header("Filters")
df_view = merged.copy()
selected_item_label = None

metric_col = None
metric_label = "Value"
metric_focus_name = "Metric"
metric_focus_short = "Metric"
vol_val_options = []
if 'qty_soldx' in df_view.columns:
    vol_val_options.append(("Volume (qty_soldx)", 'qty_soldx', 'qty_soldx sum', "Volume"))
if 'sold_amount' in df_view.columns:
    vol_val_options.append(("Value (sold_amount)", 'sold_amount', 'sold_amount sum', "Value"))

    if vol_val_options:
        metric_choice = st.sidebar.radio(
            "Metric focus",
            options=[opt[0] for opt in vol_val_options],
            index=0,
            horizontal=True if len(vol_val_options) > 1 else False,
        )
        selected_metric = next(opt for opt in vol_val_options if opt[0] == metric_choice)
        metric_col = selected_metric[1]
        metric_label = selected_metric[2]
        metric_focus_name = selected_metric[0]
        metric_focus_short = selected_metric[3]
    else:
        metric_col = next((col for col in ['qty_soldx', 'sold_amount', 'sales'] if col in df_view.columns), None)
        metric_label = {
            'qty_soldx': 'qty_soldx sum',
            'sold_amount': 'sold_amount sum',
            'sales': 'sales sum'
        }.get(metric_col, 'Value')
        metric_focus_name = metric_label.title()
        metric_focus_short = metric_focus_name

    # Brand first (multiselect)
    brand_col = next((c for c in merged.columns if "brand" in c.lower()), None)
    if brand_col:
        brands = sorted(df_view[brand_col].dropna().unique().tolist())
        selected_brands = st.sidebar.multiselect("Brand", options=brands, default=brands)
        if selected_brands:
            df_view = df_view[df_view[brand_col].isin(selected_brands)]

    # Category filter directly after Brand (multiselect)
    category_col = next((c for c in merged.columns if "category" in c.lower()), None)
    if category_col:
        categories = sorted(df_view[category_col].dropna().unique().tolist())
        selected_categories = st.sidebar.multiselect("Category", options=categories, default=categories)
        if selected_categories:
            df_view = df_view[df_view[category_col].isin(selected_categories)]

    # Region filtered by brand selection (multiselect)
    region_col = next((c for c in merged.columns if "region" in c.lower()), None)
    if region_col:
        regions = sorted(df_view[region_col].dropna().unique().tolist())
        selected_regions = st.sidebar.multiselect("Region", options=regions, default=regions)
        if selected_regions:
            df_view = df_view[df_view[region_col].isin(selected_regions)]

    # Class Code (Sales Channel) filter after Region
    class_code_col = next((c for c in merged.columns if c.lower() in {"class_code", "class code"}), None)
    if class_code_col:
        class_codes = sorted(df_view[class_code_col].dropna().unique().tolist())
        selected_class_codes = st.sidebar.multiselect("Sales Channel (Class Code)", options=class_codes, default=class_codes)
        if selected_class_codes:
            df_view = df_view[df_view[class_code_col].isin(selected_class_codes)]

    # Family filter (e.g., Brand Family) before ItemNumber
    family_col = next((c for c in merged.columns if "family" in c.lower()), None)
    if family_col:
        families = sorted(df_view[family_col].dropna().unique().tolist())
        selected_family = st.sidebar.selectbox("Family", ["All"] + families)
        if selected_family != "All":
            df_view = df_view[df_view[family_col] == selected_family]

    # ItemNumber filtered by family/brand/region + optional ItemName
    item_col = "ItemNumber" if "ItemNumber" in merged.columns else None
    item_name_col = next((c for c in merged.columns if c.lower() in {"itemname", "item_name", "name"}), None)
    if item_col:
        cols_to_keep = [item_col]
        if item_name_col:
            cols_to_keep.append(item_name_col)
        item_values = df_view[cols_to_keep].dropna(subset=[item_col])
        if item_name_col:
            unique_items_df = (
                item_values.drop_duplicates(item_col)
                .assign(
                    display=lambda df: df[item_col].astype(str).str.strip() + " - " + df[item_name_col].astype(str).str.strip()
                )
            )
            search_query = st.sidebar.text_input(
                "Search ItemNumber or Name",
                value="",
                placeholder="Type to search...",
                key="item_search_query_with_name",
            ).strip()
            filtered_df = unique_items_df
            if search_query:
                lowered = search_query.lower()
                match_mask = (
                    unique_items_df[item_col].astype(str).str.lower().str.contains(lowered, na=False)
                    | unique_items_df[item_name_col].astype(str).str.lower().str.contains(lowered, na=False)
                    | unique_items_df["display"].str.lower().str.contains(lowered, na=False)
                )
                filtered_df = unique_items_df[match_mask]
            if filtered_df.empty:
                st.sidebar.info("No items match your search. Showing all items.")
                filtered_df = unique_items_df
            item_display_map = dict(zip(unique_items_df["display"], unique_items_df[item_col]))
            item_options = ["All"] + filtered_df["display"].tolist()
            selection = st.sidebar.selectbox("ItemNumber", item_options)
            if selection != "All":
                selected_item_value = item_display_map.get(selection)
                if selected_item_value is not None:
                    selected_item_label = selection
                    df_view = df_view[df_view[item_col] == selected_item_value]
        else:
            items = sorted(item_values[item_col].unique().tolist())
            search_query = st.sidebar.text_input(
                "Search ItemNumber",
                value="",
                placeholder="Type to search...",
                key="item_search_query_number_only",
            ).strip()
            filtered_items = items
            if search_query:
                lowered = search_query.lower()
                filtered_items = [item for item in items if lowered in str(item).lower()]
            if not filtered_items:
                st.sidebar.info("No items match your search. Showing all items.")
                filtered_items = items
            selected_item = st.sidebar.selectbox("ItemNumber", ["All"] + filtered_items)
            if selected_item != "All":
                selected_item_label = f"{selected_item}"
                df_view = df_view[df_view[item_col] == selected_item]

    # Date range filter
    if has_date_column and merged['_date_dt'].notna().any():
        date_min = merged['_date_dt'].min().date()
        date_max = merged['_date_dt'].max().date()
        date_range = st.sidebar.date_input(
            "Date range",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_dt = pd.to_datetime(date_range[0])
            end_dt = pd.to_datetime(date_range[1])
            df_view = df_view[df_view['_date_dt'].between(start_dt, end_dt, inclusive='both')]

    # KPI cards rendered near the top (under page title)
    with kpi_container:
        st.markdown("---")

        total_qty = df_view['qty_soldx'].sum() if 'qty_soldx' in df_view.columns else 0
        total_returns = df_view['qty_returnedx'].sum() if 'qty_returnedx' in df_view.columns else 0
        if 'sold_amount' in df_view.columns:
            total_sales = df_view['sold_amount'].sum()
        elif 'sales' in df_view.columns:
            total_sales = df_view['sales'].sum()
        else:
            total_sales = 0
        total_discount = df_view['total_disc'].sum() if 'total_disc' in df_view.columns else 0
        returns_pct = (total_returns / total_qty * 100) if total_qty else 0
        discount_pct = (total_discount / total_sales * 100) if total_sales else 0
        kg_price = (total_sales / total_qty) if total_qty else 0
        unique_items = df_view[item_col].nunique() if item_col and item_col in df_view.columns else 0
        metric_total = df_view[metric_col].sum() if metric_col and metric_col in df_view.columns else 0
        metric_avg_per_item = metric_total / unique_items if unique_items > 0 else 0

        metric_icon = "📊"
        metric_accent = "#3949ab"
        metric_accent_rgba = "rgba(57,73,171,0.18)"
        if metric_col == 'qty_soldx':
            metric_icon = "<span style='font-weight:700;'>KG</span>"
            metric_accent = "#1e88e5"
            metric_accent_rgba = "rgba(30,136,229,0.18)"
        elif metric_col in {'sold_amount', 'sales'}:
            metric_icon = "💰"
            metric_accent = "#7b1fa2"
            metric_accent_rgba = "rgba(123,31,162,0.18)"

        total_rows = len(df_view)
        unique_brands = df_view[brand_col].nunique() if brand_col and brand_col in df_view.columns else 0
        unique_regions = df_view[region_col].nunique() if region_col and region_col in df_view.columns else 0
        date_min_display = df_view['_date_dt'].min().date().isoformat() if '_date_dt' in df_view.columns and df_view['_date_dt'].notna().any() else 'N/A'
        date_max_display = df_view['_date_dt'].max().date().isoformat() if '_date_dt' in df_view.columns and df_view['_date_dt'].notna().any() else 'N/A'
        date_range_text = f"{date_min_display} → {date_max_display}" if date_min_display != 'N/A' else 'N/A'
        months_in_view = 0
        if '_date_dt' in df_view.columns and df_view['_date_dt'].notna().any():
            months_in_view = df_view['_date_dt'].dt.to_period('M').nunique()
        monthly_metric = metric_total / months_in_view if months_in_view else 0
        monthly_qty = total_qty / months_in_view if months_in_view else 0
        monthly_returns = total_returns / months_in_view if months_in_view else 0
        monthly_sales = total_sales / months_in_view if months_in_view else 0

        st.markdown(
            """
            <style>
            .kpi-card {
                border-radius: 16px;
                padding: 0.85rem 1rem;
                background: #ffffff;
                border: 1px solid rgba(15, 23, 42, 0.05);
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 0.35rem;
                height: auto;
                min-height: auto;
                width: fit-content;
                margin: 0 auto;
            }
            .kpi-card::after {
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(135deg, rgba(255,255,255,0), rgba(255,255,255,0.2));
                pointer-events: none;
            }
            .kpi-icon {
                width: 36px;
                height: 36px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
                margin-bottom: 0.2rem;
            }
            .kpi-title {
                font-size: 0.78rem;
                font-weight: 600;
                letter-spacing: 0.05em;
                color: #475569;
                text-transform: uppercase;
            }
            .kpi-value {
                font-size: 1.5rem;
                font-weight: 700;
                color: #0f172a;
                line-height: 1.15;
                white-space: normal;
            }
            .kpi-secondary {
                font-size: 0.8rem;
                color: #c62828;
                font-weight: 600;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        def render_cards(cards):
            cols = st.columns(len(cards), gap="small")
            max_raw = max((card.get("value_raw", 0) for card in cards), default=1) or 1
            for col, card in zip(cols, cards):
                progress = card.get("value_raw", 0) / max_raw
                progress = min(max(progress, 0.08), 1)
                chip_label = card.get("chip_label", metric_focus_short)
                secondary_html = (
                    f"<div class='stat-secondary'>{card['secondary']}</div>" if card.get("secondary") else ""
                )
                card_html = textwrap.dedent(
                    f"""
                    <style>
                        .tile-wrapper {{
                            background: #fff;
                            border-radius: 20px;
                            padding: 1.1rem 1.25rem;
                            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
                            color: #0f172a;
                            border: 1px solid rgba(15, 23, 42, 0.08);
                            display: flex;
                            flex-direction: column;
                            gap: 0.45rem;
                        }}
                        .tile-header {{
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            gap: 0.75rem;
                        }}
                        .tile-group {{
                            display: flex;
                            align-items: center;
                            gap: 0.55rem;
                        }}
                        .tile-icon {{
                            width: 36px;
                            height: 36px;
                            border-radius: 12px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: 1.1rem;
                            background: {card["accent_rgba"]};
                            color: {card["accent"]};
                        }}
                        .tile-label {{
                            font-size: 0.78rem;
                            font-weight: 600;
                            letter-spacing: 0.08em;
                            color: #475569;
                        }}
                        .tile-chip {{
                            padding: 0.15rem 0.65rem;
                            border-radius: 999px;
                            font-size: 0.72rem;
                            font-weight: 600;
                            text-transform: uppercase;
                            background: rgba(15, 23, 42, 0.08);
                            color: #0f172a;
                        }}
                        .tile-value {{
                            font-size: 2.05rem;
                            font-weight: 700;
                            color: #0f172a;
                            line-height: 1.1;
                        }}
                        .tile-secondary {{
                            font-size: 0.85rem;
                            color: #64748b;
                            font-weight: 600;
                        }}
                        .tile-progress {{
                            height: 6px;
                            width: 100%;
                            border-radius: 999px;
                            background: rgba(15, 23, 42, 0.08);
                            overflow: hidden;
                        }}
                        .tile-progress-bar {{
                            height: 100%;
                            width: {progress*100:.0f}%;
                            background: {card["accent"]};
                            border-radius: inherit;
                            transition: width 0.4s ease;
                        }}
                    </style>
                    <div class='tile-wrapper'>
                        <div class='tile-header'>
                            <div class='tile-group'>
                                <div class='tile-icon'>{card["icon"]}</div>
                                <div>
                                    <div class='tile-label'>{card["title"].upper()}</div>
                                    <div class='tile-chip'>{chip_label}</div>
                                </div>
                            </div>
                            <span style='font-size:0.78rem;font-weight:600;color:{card["accent"]};'>Live</span>
                        </div>
                        <div class='tile-value' style='{card.get("value_style", "")}'>{card["value"]}</div>
                        {secondary_html or ""}
                        <div class='tile-progress'>
                            <div class='tile-progress-bar'></div>
                        </div>
                    </div>
                    """
                ).strip()
                with col:
                    components.html(card_html, height=240, scrolling=False)

        primary_cards = [
            {
                "icon": metric_icon,
                "title": f"Total {metric_focus_short}",
                "value": f"{metric_total:,.0f}",
                "secondary": None,
                "accent": metric_accent,
                "accent_rgba": metric_accent_rgba,
            },
            {
                "icon": "↩️",
                "title": "qty_returnedx",
                "value": f"{total_returns:,.0f}",
                "secondary": f"{returns_pct:.1f}% of Volume" if total_qty else None,
                "accent": "#e53935",
                "accent_rgba": "rgba(229,57,53,0.18)",
            },
            {
                "icon": "🎯",
                "title": "total_disc",
                "value": f"{total_discount:,.0f}",
                "secondary": f"{discount_pct:.1f}% of sold_amount" if total_sales else None,
                "accent": "#d81b60",
                "accent_rgba": "rgba(216,27,96,0.18)",
            },
        ]

        if metric_col != 'qty_soldx' and 'qty_soldx' in df_view.columns:
            primary_cards.insert(1, {
                "icon": "<span style='font-weight:700;'>KG</span>",
                "title": "Total qty_soldx",
                "value": f"{total_qty:,.0f}",
                "secondary": None,
                "accent": "#1e88e5",
                "accent_rgba": "rgba(30,136,229,0.18)",
            })

        if metric_col not in {'sold_amount', 'sales'} and total_sales:
            primary_cards.append({
                "icon": "💰",
                "title": "Total sold_amount",
                "value": f"{total_sales:,.0f}",
                "secondary": None,
                "accent": "#7b1fa2",
                "accent_rgba": "rgba(123,31,162,0.18)",
            })

        secondary_cards = [
            {
                "icon": "⚖️",
                "title": "Avg KG Price",
                "value": f"{kg_price:,.2f}",
                "secondary": "sold_amount ÷ qty_soldx" if total_qty else None,
                "accent": "#00897b",
                "accent_rgba": "rgba(0,137,123,0.18)",
            },
            {
                "icon": "📊",
                "title": f"Avg {metric_focus_short} / item",
                "value": f"{metric_avg_per_item:,.1f}",
                "secondary": f"Across {unique_items:,} SKUs" if unique_items else None,
                "accent": "#fb8c00",
                "accent_rgba": "rgba(251,140,0,0.2)",
            },
            {
                "icon": "🧾",
                "title": "Unique Items",
                "value": f"{unique_items:,}",
                "secondary": None,
                "accent": "#3949ab",
                "accent_rgba": "rgba(57,73,171,0.18)",
            },
        ]

        render_cards(primary_cards)
        render_cards(secondary_cards)

        monthly_cards = []
        if months_in_view:
            if metric_total:
                monthly_cards.append({
                    "icon": "🗓️",
                    "title": f"Monthly {metric_focus_short}",
                    "value": f"{monthly_metric:,.1f}",
                    "secondary": f"Avg over {months_in_view} months",
                    "accent": metric_accent,
                    "accent_rgba": metric_accent_rgba,
                })
            if total_qty:
                monthly_cards.append({
                    "icon": "📦",
                    "title": "Monthly Volume",
                    "value": f"{monthly_qty:,.1f}",
                    "secondary": f"Across {months_in_view} months",
                    "accent": "#1e88e5",
                    "accent_rgba": "rgba(30,136,229,0.18)",
                })
            if total_returns:
                monthly_cards.append({
                    "icon": "↩️",
                    "title": "Monthly Returns",
                    "value": f"{monthly_returns:,.1f}",
                    "secondary": f"Across {months_in_view} months",
                    "accent": "#e53935",
                    "accent_rgba": "rgba(229,57,53,0.18)",
                })
            if monthly_sales:
                monthly_cards.append({
                    "icon": "💵",
                    "title": "Monthly sold_amount",
                    "value": f"{monthly_sales:,.1f}",
                    "secondary": f"Across {months_in_view} months",
                    "accent": "#7b1fa2",
                    "accent_rgba": "rgba(123,31,162,0.18)",
                })

        if monthly_cards:
            render_cards(monthly_cards)

        st.markdown("---")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Forecast Options")
    forecast_horizon = st.sidebar.slider("Forecast horizon (months)", min_value=6, max_value=24, value=12, step=1)
    trend_mode = st.sidebar.selectbox("Trend component", options=["add", "mul"], index=0)
    seasonal_mode = st.sidebar.selectbox("Seasonal component", options=["add", "mul"], index=0)
    manual_growth_pct = st.sidebar.number_input(
        "Manual growth override (%)",
        min_value=-100.0,
        max_value=200.0,
        value=0.0,
        step=0.1,
        format="%.1f"
    )

    if 'show_filtered_data' not in st.session_state:
        st.session_state['show_filtered_data'] = False

    toggle_label = "Hide Filtered Data" if st.session_state['show_filtered_data'] else "Show Filtered Data"
    if st.sidebar.button(toggle_label):
        st.session_state['show_filtered_data'] = not st.session_state['show_filtered_data']

    if st.session_state['show_filtered_data']:
        st.subheader("Filtered Data")
        st.dataframe(df_view)

        st.sidebar.download_button(
            label="Download Filtered Data",
            data=df_view.to_csv(index=False).encode("utf-8"),
            file_name="filtered_data.csv",
            mime="text/csv"
        )

    def render_group_bar(group_col, label):
        if not group_col or group_col not in df_view.columns:
            st.info(f"{label} column not available in the current dataset.")
            return
        if not metric_col:
            st.info("No numeric metric (qty_soldx, sold_amount, or sales) available for charting.")
            return

        grouped = (
            df_view.dropna(subset=[group_col])
            .groupby(group_col)[metric_col]
            .sum()
            .reset_index(name='value')
        )
        grouped = grouped[grouped['value'] != 0]

        if grouped.empty:
            st.info(f"No data to display for {label.lower()} after applying filters.")
            return

        grouped = grouped.sort_values('value', ascending=False)
        total_value = grouped['value'].sum()
        grouped['pct'] = grouped['value'] / total_value * 100 if total_value else 0
        grouped['pct_label'] = grouped['pct'].map(lambda v: f"{v:.1f}%")
        max_value = grouped['value'].max()
        base_unit = max(max_value * 0.01, 0.5) if pd.notna(max_value) else 1
        grouped['label_chars'] = grouped['pct_label'].str.len().clip(lower=1)
        grouped['label_pad'] = grouped['label_chars'] * base_unit + base_unit
        grouped['label_x2'] = grouped['value'] + grouped['label_pad']
        grouped['label_center'] = grouped['value'] + (grouped['label_pad'] / 2)
        grouped['label_text'] = grouped['pct_label']
        chart_height = min(60 * len(grouped), 420)
        base = alt.Chart(grouped)
        bars = (
            base
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X('value:Q', title=metric_label),
                y=alt.Y(f'{group_col}:N', sort='-x', title=label),
                color=alt.Color(f'{group_col}:N', legend=None),
                tooltip=[
                    alt.Tooltip(f'{group_col}:N', title=label),
                    alt.Tooltip('value:Q', title=metric_label, format=',.0f'),
                    alt.Tooltip('pct:Q', title='% Share', format='.1f')
                ]
            )
        )
        label_bg = (
            base
            .mark_bar(color='#ffffff', stroke='#e2e8f0', strokeWidth=1, cornerRadius=6)
            .encode(
                x=alt.X('value:Q'),
                x2=alt.X2('label_x2:Q'),
                y=alt.Y(f'{group_col}:N', sort='-x')
            )
        )
        labels = (
            base
            .mark_text(color='#0f172a', fontWeight=600)
            .encode(
                x=alt.X('label_center:Q'),
                y=alt.Y(f'{group_col}:N', sort='-x'),
                text='label_text:N'
            )
        )

        chart = (bars + label_bg + labels).properties(height=chart_height)

        st.altair_chart(chart, use_container_width=True)

    group_sections = []
    if region_col and region_col in df_view.columns:
        group_sections.append(("Region Performance", region_col))
    if class_code_col and class_code_col in df_view.columns:
        group_sections.append(("Sales Channel Performance", class_code_col))
    if family_col and family_col in df_view.columns:
        group_sections.append(("Family Performance", family_col))

    if group_sections and metric_col:
        st.markdown("---")
        # Build brief filter summary
        filter_parts = []
        if brand_col and brand_col in df_view.columns and 'selected_brands' in locals() and selected_brands != brands:
            filter_parts.append(f"{len(selected_brands)} Brands")
        if category_col and category_col in df_view.columns and 'selected_categories' in locals() and selected_categories != categories:
            filter_parts.append(f"{len(selected_categories)} Categories")
        if region_col and region_col in df_view.columns and 'selected_regions' in locals() and selected_regions != regions:
            filter_parts.append(f"{len(selected_regions)} Regions")
        if class_code_col and class_code_col in df_view.columns and 'selected_class_codes' in locals() and selected_class_codes != class_codes:
            filter_parts.append(f"{len(selected_class_codes)} Sales Channels")
        if family_col and family_col in df_view.columns and 'selected_family' in locals() and selected_family != "All":
            filter_parts.append(f"Family: {selected_family}")
        if item_col and item_col in df_view.columns and 'selection' in locals() and selection != "All":
            filter_parts.append(f"Item: {selection}")
        
        filter_summary = " | ".join(filter_parts) if filter_parts else "All Data"
        st.subheader(f"Performance by {filter_summary}")

        if len(group_sections) == 3:
            col_left, col_mid, col_right = st.columns(3)
            with col_left:
                st.markdown("**Region Performance**")
                render_group_bar(group_sections[0][1], "Region")
            with col_mid:
                st.markdown("**Sales Channel Performance**")
                render_group_bar(group_sections[1][1], "Sales Channel")
            with col_right:
                st.markdown("**Family Performance**")
                render_group_bar(group_sections[2][1], "Family")
        elif len(group_sections) == 2:
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown(f"**{group_sections[0][0]}**")
                render_group_bar(group_sections[0][1], group_sections[0][0].split()[0])
            with col_right:
                st.markdown(f"**{group_sections[1][0]}**")
                render_group_bar(group_sections[1][1], group_sections[1][0].split()[0])
        else:
            label, column_name = group_sections[0]
            st.markdown(f"**{label}**")
            render_group_bar(column_name, label.split()[0])
    elif not metric_col:
        st.info("Cannot build group charts because no qty_soldx, sold_amount, or sales columns were found.")

    if metric_col and metric_col in df_view.columns and item_col and item_col in df_view.columns:
        item_name_lookup = None
        if item_name_col and item_name_col in df_view.columns:
            item_name_lookup = (
                df_view[[item_col, item_name_col]]
                .dropna(subset=[item_col])
                .drop_duplicates(item_col)
                .set_index(item_col)[item_name_col]
                .to_dict()
            )

        abc_source = (
            df_view.groupby(item_col)[metric_col]
            .sum()
            .reset_index(name='metric_total')
            .sort_values('metric_total', ascending=False)
        )
        abc_source = abc_source[abc_source['metric_total'] > 0]

        if not abc_source.empty:
            overall_total = abc_source['metric_total'].sum()
            if overall_total == 0:
                st.info("ABC-XYZ matrix unavailable because the current metric totals zero after filters.")
            else:
                abc_source['cumulative_pct'] = abc_source['metric_total'].cumsum() / overall_total * 100

                def classify_abc(pct):
                    if pct <= 80:
                        return "A"
                    elif pct <= 95:
                        return "B"
                    return "C"

                abc_source['ABC'] = abc_source['cumulative_pct'].apply(classify_abc)

                xyz_source = None
                if '_date_dt' in df_view.columns and df_view['_date_dt'].notna().any():
                    monthly_item = (
                        df_view.dropna(subset=['_date_dt'])
                        .assign(month=lambda d: d['_date_dt'].dt.to_period('M').dt.to_timestamp())
                        .groupby([item_col, 'month'])[metric_col]
                        .sum()
                        .reset_index(name='monthly_metric')
                    )
                    if not monthly_item.empty:
                        variability = (
                            monthly_item.groupby(item_col)['monthly_metric']
                            .agg(['mean', 'std'])
                            .reset_index()
                            .rename(columns={'mean': 'mean_metric', 'std': 'std_metric'})
                        )
                        variability['std_metric'] = variability['std_metric'].fillna(0)
                        variability['cv'] = variability.apply(
                            lambda row: row['std_metric'] / row['mean_metric'] if row['mean_metric'] else float('inf'),
                            axis=1,
                        )

                        def classify_xyz(cv):
                            if cv <= 0.5:
                                return "X"
                            elif cv <= 1.0:
                                return "Y"
                            return "Z"

                        variability['XYZ'] = variability['cv'].apply(classify_xyz)
                        xyz_source = variability[[item_col, 'XYZ', 'cv']]

                if xyz_source is not None:
                    classification_result = abc_source.merge(xyz_source, on=item_col, how='left')
                else:
                    classification_result = abc_source.assign(cv=pd.NA, XYZ="Z")

                classification_result['XYZ'] = classification_result['XYZ'].fillna("Z")
                classification_result['share_pct'] = classification_result['metric_total'] / overall_total * 100
                if item_name_lookup:
                    classification_result['ItemDisplay'] = classification_result[item_col].apply(
                        lambda code: f"{code} - {item_name_lookup.get(code, '')}".strip(" -")
                    )
                else:
                    classification_result['ItemDisplay'] = classification_result[item_col].astype(str)

                matrix = (
                    classification_result.groupby(['ABC', 'XYZ'])
                    .agg(
                        items_count=(item_col, 'nunique'),
                        metric_total=('metric_total', 'sum'),
                        share_pct=('share_pct', 'sum'),
                    )
                    .reset_index()
                )

                class_items = (
                    classification_result.groupby(['ABC', 'XYZ'])['ItemDisplay']
                    .apply(
                        lambda s: ", ".join(s.astype(str).head(3))
                        + (" …" if len(s) > 3 else "")
                    )
                    .reset_index(name='items_preview')
                )
                matrix = matrix.merge(class_items, on=['ABC', 'XYZ'], how='left')

                matrix['ABC'] = pd.Categorical(matrix['ABC'], categories=['A', 'B', 'C'], ordered=True)
                matrix['XYZ'] = pd.Categorical(matrix['XYZ'], categories=['X', 'Y', 'Z'], ordered=True)
                matrix = matrix.sort_values(['ABC', 'XYZ'])

                st.markdown("---")
                st.subheader("ABC-XYZ Item Matrix")

                if xyz_source is None:
                    st.caption("XYZ classes default to Z because there is no date granularity to measure demand variability.")

                chart = (
                    alt.Chart(matrix)
                    .mark_circle()
                    .encode(
                        x=alt.X('ABC:N', sort=['A', 'B', 'C'], title='ABC Class (Value Contribution)'),
                        y=alt.Y('XYZ:N', sort=['X', 'Y', 'Z'], title='XYZ Class (Demand Variability)'),
                        size=alt.Size('metric_total:Q', title=f'Total {metric_focus_short}', scale=alt.Scale(range=[50, 900])),
                        color=alt.Color(
                            'ABC:N',
                            legend=None,
                            scale=alt.Scale(
                                domain=['A', 'B', 'C'],
                                range=['#66d9e8', '#ffd166', '#ff6b6b'],
                            ),
                        ),
                        tooltip=[
                            alt.Tooltip('ABC:N', title='ABC Class'),
                            alt.Tooltip('XYZ:N', title='XYZ Class'),
                            alt.Tooltip('items_count:Q', title='Items'),
                            alt.Tooltip('share_pct:Q', title='% of Total', format='.1f'),
                            alt.Tooltip('items_preview:N', title='Sample Items'),
                        ],
                    )
                    .properties(height=320)
                )

                labels = (
                    alt.Chart(matrix)
                    .mark_text(fontWeight=600, color='#f8fafc')
                    .encode(
                        x='ABC:N',
                        y='XYZ:N',
                        text='items_preview:N',
                    )
                )

                layered_chart = (chart + labels).configure_view(
                    strokeWidth=0,
                ).configure(background='#0b1220')
                st.altair_chart(layered_chart, use_container_width=True)

                display_df = classification_result[[item_col, 'ItemDisplay', 'metric_total', 'share_pct', 'ABC', 'XYZ', 'cv']].copy()
                display_df = display_df.sort_values(['ABC', 'metric_total'], ascending=[True, False])
                display_df.rename(
                    columns={
                        item_col: "ItemNumber",
                        'ItemDisplay': "Item",
                        'metric_total': f'Total {metric_focus_short}',
                        'share_pct': '% Contribution',
                        'cv': 'CV',
                    },
                    inplace=True,
                )
                display_df['% Contribution'] = display_df['% Contribution'].map(lambda v: f"{v:.1f}%")
                if display_df['CV'].notna().any():
                    display_df['CV'] = display_df['CV'].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
                st.dataframe(display_df.head(25))
        else:
            st.info("Not enough item-level data after filters to compute ABC-XYZ classification.")

    # Plot selected metric over time for the currently filtered dataset
    if metric_col and metric_col in df_view.columns and ('_date_dt' in df_view.columns or date_col_name):
        st.subheader(f"{metric_focus_short} Trend")
        chart_df = df_view.copy()
        if '_date_dt' in chart_df.columns:
            chart_df['date'] = chart_df['_date_dt']
        else:
            chart_df['date'] = pd.to_datetime(chart_df[date_col_name], errors='coerce')
        chart_df = chart_df.dropna(subset=['date'])

        if not chart_df.empty:
            monthly = (
                chart_df
                .groupby(chart_df['date'].dt.to_period('M').dt.to_timestamp())[metric_col]
                .sum()
                .reset_index()
                .rename(columns={'date': 'Month', metric_col: 'MetricValue'})
            )
            monthly = monthly.sort_values('Month')
            monthly['Year'] = monthly['Month'].dt.year
            monthly['MonthStart'] = monthly['Month']

            training_min = monthly['MonthStart'].min().date()
            training_max = monthly['MonthStart'].max().date()
            training_selection = st.sidebar.date_input(
                "Forecast training window",
                value=(training_min, training_max),
                min_value=training_min,
                max_value=training_max
            )

            if isinstance(training_selection, tuple) and len(training_selection) == 2:
                training_start = pd.to_datetime(training_selection[0])
                training_end = pd.to_datetime(training_selection[1])
            else:
                training_start = pd.to_datetime(training_selection)
                training_end = training_start

            if training_start > training_end:
                training_start, training_end = training_end, training_start

            monthly_training = monthly[
                (monthly['MonthStart'] >= training_start) & (monthly['MonthStart'] <= training_end)
            ]

            chart = (
                alt.Chart(monthly)
                .mark_line(point=True)
                .encode(
                    x=alt.X('MonthStart:T', title='Month', axis=alt.Axis(format='%Y-%m')),
                    y=alt.Y('MetricValue:Q', title=metric_label),
                    color=alt.Color('Year:N', title='Year'),
                    tooltip=[
                        alt.Tooltip('Year:N', title='Year'),
                        alt.Tooltip('MonthStart:T', title='Month', format='%Y-%m'),
                        alt.Tooltip('MetricValue:Q', title=metric_label, format=',.0f')
                    ]
                )
                .properties(height=350)
            )

            st.altair_chart(chart, use_container_width=True)

            # Seasonal index chart for the same filtered data
            seasonal_df = chart_df.copy()
            seasonal_df['MonthNum'] = seasonal_df['date'].dt.month
            seasonal_summary = (
                seasonal_df
                .groupby('MonthNum')[metric_col]
                .mean()
                .reset_index(name='avg_metric')
            )

            if not seasonal_summary.empty:
                seasonal_summary['MonthLabel'] = seasonal_summary['MonthNum'].apply(lambda m: calendar.month_abbr[m])
                overall_mean = seasonal_summary['avg_metric'].mean()

                if overall_mean and overall_mean != 0:
                    seasonal_summary['SeasonalIndex'] = seasonal_summary['avg_metric'] / overall_mean
                    month_order = [calendar.month_abbr[i] for i in range(1, 13)]

                    season_chart = (
                        alt.Chart(seasonal_summary)
                        .mark_bar()
                        .encode(
                            x=alt.X('MonthLabel:N', sort=month_order, title='Month'),
                            y=alt.Y('SeasonalIndex:Q', title='Seasonal Index'),
                            color=alt.Color('SeasonalIndex:Q', title='Index', scale=alt.Scale(scheme='blues')),
                            tooltip=[
                                alt.Tooltip('MonthLabel:N', title='Month'),
                                alt.Tooltip('avg_metric:Q', title=f'Avg {metric_focus_short}', format=',.0f'),
                                alt.Tooltip('SeasonalIndex:Q', title='Seasonal Index', format='.2f')
                            ]
                        )
                        .properties(height=300)
                    )

                    st.subheader("Seasonal Index (Monthly)")
                    st.altair_chart(season_chart, use_container_width=True)
                else:
                    st.info("Not enough variation to calculate a seasonal index for the current filters.")
            else:
                st.info("Not enough data to calculate a seasonal index for the current filters.")

            # Forecast using Holt-Winters with user parameters
            if ExponentialSmoothing is None:
                st.info(
                    "Forecasts require the `statsmodels` package. "
                    "Please add `statsmodels` to your Streamlit Cloud requirements file to enable this section."
                )
            elif len(monthly_training) >= 12:
                st.subheader(f"{forecast_horizon}-Month Forecast")
                try:
                    monthly_ts = monthly_training.set_index('MonthStart')['MetricValue']
                    monthly_ts = monthly_ts.resample('MS').sum()

                    model = ExponentialSmoothing(
                        monthly_ts,
                        trend=trend_mode,
                        seasonal=seasonal_mode,
                        seasonal_periods=12,
                        initialization_method='estimated'
                    )
                    fitted_model = model.fit(optimized=True)
                    forecast = fitted_model.forecast(forecast_horizon)

                    # Apply manual growth override if specified
                    if manual_growth_pct != 0.0:
                        growth_factor = 1 + manual_growth_pct / 100
                        forecast = forecast * growth_factor

                    actual_df = monthly_ts.reset_index().rename(columns={'MonthStart': 'Month', 'MetricValue': 'MetricValue'})
                    actual_df['Type'] = 'Actual'

                    forecast_df = forecast.reset_index().rename(columns={'index': 'Month', 0: 'MetricValue'})
                    forecast_df['Type'] = 'Forecast'

                    forecast_df['Month'] = pd.to_datetime(forecast_df['Month'])
                    display_df = pd.concat([actual_df, forecast_df], ignore_index=True)

                    forecast_chart = (
                        alt.Chart(display_df)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X('Month:T', title='Month', axis=alt.Axis(format='%Y-%m')),
                            y=alt.Y('MetricValue:Q', title=metric_focus_short),
                            color=alt.Color('Type:N', title='Series'),
                            strokeDash=alt.condition(
                                alt.FieldEqualPredicate(field='Type', equal='Forecast'),
                                alt.value([5, 5]),
                                alt.value([0])
                            ),
                            tooltip=[
                                alt.Tooltip('Type:N'),
                                alt.Tooltip('Month:T', format='%Y-%m'),
                                alt.Tooltip('MetricValue:Q', title=metric_focus_short, format=',.0f')
                            ]
                        )
                        .properties(height=350)
                    )

                    st.altair_chart(forecast_chart, use_container_width=True)

                    csv_data = display_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Forecast Results",
                        data=csv_data,
                        file_name=f"forecast_results_{metric_col}.csv",
                        mime="text/csv"
                    )

                    # Yearly growth (historical + forecast)
                    hist_growth = (
                        monthly_training.assign(Year=monthly_training['MonthStart'].dt.year)
                        .groupby('Year')['MetricValue']
                        .sum()
                        .reset_index(name='TotalMetric')
                        .sort_values('Year')
                    )
                    hist_growth['Type'] = 'Actual'

                    forecast_yearly = (
                        forecast_df.assign(Year=forecast_df['Month'].dt.year)
                        .groupby('Year')['MetricValue']
                        .sum()
                        .reset_index(name='TotalMetric')
                        .sort_values('Year')
                    )
                    forecast_yearly['Type'] = 'Forecast'

                    growth_df = pd.concat([hist_growth, forecast_yearly], ignore_index=True)
                    growth_df = (
                        growth_df
                        .groupby('Year', as_index=False)
                        .agg({'TotalMetric': 'sum', 'Type': lambda x: 'Actual+Forecast' if len(set(x)) > 1 else x.iloc[0]})
                    )
                    growth_df = growth_df.sort_values('Year').reset_index(drop=True)
                    growth_df['YoYPercent'] = growth_df['TotalMetric'].pct_change() * 100

                    st.subheader("Yearly Growth (Actual vs Forecast)")
                    growth_chart = (
                        alt.Chart(growth_df)
                        .mark_bar()
                        .encode(
                            x=alt.X('Year:O', title='Year'),
                            y=alt.Y('TotalMetric:Q', title=f'Total {metric_focus_short}'),
                            color=alt.Color('Type:N', title='Series'),
                            tooltip=[
                                alt.Tooltip('Year:O', title='Year'),
                                alt.Tooltip('Type:N'),
                                alt.Tooltip('TotalMetric:Q', title=f'Total {metric_focus_short}', format=',.0f'),
                                alt.Tooltip('YoYPercent:Q', title='YoY %', format='.2f')
                            ]
                        )
                        .properties(height=320)
                    )
                    st.altair_chart(growth_chart, use_container_width=True)

                    pretty_growth = growth_df.copy()
                    pretty_growth['YoY %'] = pretty_growth['YoYPercent'].map(lambda v: f"{v:.2f}%" if pd.notna(v) else '—')
                    pretty_growth = pretty_growth.rename(columns={'TotalMetric': f'Total {metric_focus_short}'})
                    st.dataframe(pretty_growth[['Year', 'Type', f'Total {metric_focus_short}', 'YoY %']])

                    st.download_button(
                        label="Download Yearly Growth",
                        data=pretty_growth.to_csv(index=False).encode('utf-8'),
                        file_name=f"yearly_growth_{metric_col}.csv",
                        mime="text/csv"
                    )

                    st.caption(
                        "Forecast uses Holt-Winters with your selected trend/seasonal options on the filtered monthly totals. "
                        f"Manual growth override: {manual_growth_pct:.1f}%." if manual_growth_pct != 0.0 else
                        "Forecast uses Holt-Winters with your selected trend/seasonal options on the filtered monthly totals."
                    )
                except Exception as forecast_error:
                    st.warning(f"Unable to compute forecast: {forecast_error}")
            else:
                st.info("Need at least 12 months in the selected historical window to build a forecast for the current filters.")
        else:
            st.info("No valid date values available to plot for the current filters.")
    else:
        st.info("Selected metric or date column not available, so the trend chart cannot be displayed.")
