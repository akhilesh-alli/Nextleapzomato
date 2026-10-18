"""
ui/streamlit_app.py
--------------------
Streamlit Web Application for the AI Restaurant Recommendation System.
Provides a modern, responsive web dashboard with sidebar preferences,
progress indicators, card-based recommendations, and session-state caching.

Features:
  - Sidebar preference configuration with autocomplete pills
  - EC-701: Required location input check
  - EC-702: Session-state caching to prevent duplicate LLM calls on re-render
  - Styled card expanders with rating badges and cuisine chips
  - Comparative AI summary block
  - Pipeline performance telemetry
"""

import sys
import pathlib

# Ensure project root is in sys.path
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from config.settings import LLM_MODEL, LLM_PROVIDER
from src.filtering.models import UserPreferences
from src.orchestrator import Orchestrator, RecommendationResult


# ── Page Configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Restaurant Concierge | Zomato Insights",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS Styling (Obsidian Gourmet Concierge Theme) ──────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    /* Global Streamlit Dark Theme Overrides */
    .stApp {
        background-color: #0B0F17 !important;
        color: #dfe2ee !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, #1c2028 0%, #131B2E 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 2rem 2.5rem;
        border-radius: 20px;
        color: #F8FAFC;
        margin-bottom: 2rem;
        box-shadow: 0 12px 32px -4px rgba(0, 0, 0, 0.6);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: -30px;
        right: -30px;
        width: 140px;
        height: 140px;
        background: rgba(6, 182, 212, 0.15);
        border-radius: 999px;
        filter: blur(40px);
    }
    .main-header h1 {
        color: #F8FAFC !important;
        font-weight: 800;
        margin-bottom: 0.5rem;
        font-size: 2.2rem;
        letter-spacing: -0.02em;
    }
    .main-header h1 span {
        color: #06B6D4;
    }
    .main-header p {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 0;
        line-height: 1.6;
    }
    
    /* Expander / Card Styling */
    div[data-testid="stExpander"] {
        background: #181c24 !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5) !important;
        margin-bottom: 1rem;
    }
    
    /* Badges */
    .restaurant-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-rating {
        background-color: #00a572;
        color: #ffffff;
    }
    .badge-cost {
        background-color: rgba(6, 182, 212, 0.15);
        color: #4cd7f6;
        border: 1px solid rgba(6, 182, 212, 0.3);
    }
    .badge-cuisine {
        background-color: #262a33;
        color: #dfe2ee;
    }
    
    .why-box {
        background: rgba(10, 14, 22, 0.85);
        border-left: 4px solid #ff5169;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin-top: 10px;
        color: #F8FAFC;
        line-height: 1.6;
        font-size: 0.95rem;
    }
    
    .summary-card {
        background: linear-gradient(135deg, #1c2028 0%, #181c24 100%);
        border: 1px solid rgba(6, 182, 212, 0.25);
        border-radius: 16px;
        padding: 1.75rem;
        margin-top: 1.5rem;
        box-shadow: 0 8px 32px rgba(6, 182, 212, 0.1);
    }
    
    .web-launcher-banner {
        background: rgba(6, 182, 212, 0.1);
        border: 1px solid rgba(6, 182, 212, 0.3);
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
</style>
""", unsafe_allow_html=True)


# ── Cached Orchestrator Resource ─────────────────────────────────────────────

@st.cache_resource(show_spinner="Initializing recommendation engine & data...")
def get_orchestrator() -> Orchestrator:
    """Load and cache the Orchestrator instance once per application session."""
    return Orchestrator(lazy_load=False)


# ── Session State Management (EC-702) ────────────────────────────────────────

if "result" not in st.session_state:
    st.session_state.result = None

if "last_query" not in st.session_state:
    st.session_state.last_query = ""


# ── Sidebar: Preference Collection ───────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/b/bd/Zomato_Logo.svg",
        width=160,
    )
    st.title("Dining Preferences")
    st.caption(f"Powered by **{LLM_PROVIDER.upper()}** ({LLM_MODEL})")

    st.markdown("---")

    # 1. Location (EC-701)
    location_input = st.text_input(
        "📍 Location / Area *",
        value=st.session_state.get("sidebar_loc", "Koramangala, Bangalore"),
        help="City or neighborhood name (e.g. Bangalore, Indiranagar, Koramangala, Delhi)",
    )

    # Quick pills for common Bangalore locations
    col_p1, col_p2, col_p3 = st.columns(3)
    if col_p1.button("Koramangala"):
        location_input = "Koramangala"
    if col_p2.button("Indiranagar"):
        location_input = "Indiranagar"
    if col_p3.button("Whitefield"):
        location_input = "Whitefield"

    # 2. Cuisine
    cuisine_input = st.text_input(
        "🍜 Preferred Cuisine",
        placeholder="e.g. Italian, North Indian, Biryani, Cafe",
        help="Leave blank to explore all cuisines",
    )

    # 3. Budget Tier (EC-202)
    budget_options = {
        "Any Budget": "",
        "Low (Under ₹300 for two)": "low",
        "Medium (₹300 - ₹800 for two)": "medium",
        "High (Above ₹800 for two)": "high",
    }
    budget_label = st.selectbox("💳 Budget Tier", list(budget_options.keys()), index=2)
    selected_budget = budget_options[budget_label]

    # 4. Minimum Rating (EC-201)
    min_rating = st.slider(
        "⭐ Minimum Rating",
        min_value=0.0,
        max_value=5.0,
        value=3.8,
        step=0.1,
    )

    # 5. Service Features
    col_del, col_book = st.columns(2)
    with col_del:
        online_delivery = st.checkbox("🛵 Delivery", value=False)
    with col_book:
        table_booking = st.checkbox("📅 Table Booking", value=False)

    # 6. Additional Notes (EC-203, EC-403)
    extra_notes = st.text_area(
        "📝 Additional Notes / Vibe",
        placeholder="e.g. rooftop view, quiet for conversation, outdoor seating, quick service",
        max_chars=200,
        help="Maximum 200 characters.",
    )

    st.markdown("---")
    find_button = st.button("🔍 Find Recommendations", type="primary", use_container_width=True)


# ── Main Content Area ────────────────────────────────────────────────────────

st.markdown("""
<div class="web-launcher-banner">
    <div>
        <strong style="color:#4cd7f6;">✨ New Obsidian Concierge UI Available!</strong>
        <span style="color:#dfe2ee; margin-left: 8px;">Run <code>python run_web.py</code> to launch the full-featured, pixel-perfect Stitch AI frontend at <code>http://127.0.0.1:8000</code>.</span>
    </div>
</div>
<div class="main-header">
    <h1>Zomato Concierge <span>AI</span></h1>
    <p>Discover personalized dining experiences matching your taste, budget, and vibe using real Zomato data and intelligent neural reasoning.</p>
</div>
""", unsafe_allow_html=True)


# ── Trigger Recommendation Pipeline ──────────────────────────────────────────

if find_button:
    # EC-701: Location required validation
    if not location_input or not location_input.strip():
        st.error("⚠️ **Location is required.** Please enter a city or neighborhood (e.g. Bangalore, Indiranagar) in the sidebar.")
    else:
        prefs = UserPreferences(
            location=location_input.strip(),
            budget=selected_budget,
            cuisine=cuisine_input.strip(),
            min_rating=float(min_rating),
            online_delivery=online_delivery,
            table_booking=table_booking,
            extra_notes=extra_notes.strip(),
        )

        with st.spinner("🤖 Consulting Zomato database and generating personalized recommendations..."):
            try:
                orchestrator = get_orchestrator()
                # Store in session state to prevent re-execution on re-render (EC-702)
                st.session_state.result = orchestrator.recommend(prefs)
                st.session_state.last_query = f"{prefs.location} | {prefs.budget or 'any budget'} | {prefs.cuisine or 'any cuisine'}"
            except Exception as err:
                st.error(f"An unexpected error occurred while processing your request: {err}")


# ── Render Cached Results ────────────────────────────────────────────────────

result: RecommendationResult = st.session_state.result

if result is not None:
    # Query summary chips
    if st.session_state.last_query:
        st.caption(f"Showing results for: **{st.session_state.last_query}**")

    # Error case
    if result.error:
        st.warning(f"⚠️ {result.error}")
    
    # Filter relaxation notice
    elif result.filter_result and result.filter_result.relaxed:
        st.info(f"ℹ️ **Smart Search Adjustment:** {result.filter_result.relaxation_note}")

    # Fallback notice
    if result.is_fallback and result.is_success:
        st.warning("⚠️ **AI Service Notice:** AI explanations are currently unavailable. Displaying top-rated verified matches from the database.")

    # Render recommendations
    if result.has_recommendations:
        st.subheader(f"Top {len(result.recommendations)} Curated Dining Spots")

        for r in result.recommendations:
            with st.expander(f"**#{r.rank}  {r.name}** — ⭐ {r.rating:.1f}/5.0 | ₹{r.cost} for two", expanded=(r.rank == 1)):
                col_info, col_exp = st.columns([1, 2])

                with col_info:
                    st.markdown(f"**📍 Location:** {r.location or 'Bangalore'}")
                    st.markdown(f"**🍜 Cuisine:** {r.cuisine or 'Multi-cuisine'}")
                    st.markdown(f"**⭐ Rating:** {r.rating:.1f} / 5.0")
                    st.markdown(f"**💳 Estimated Cost:** ₹{r.cost} for two")

                with col_exp:
                    st.markdown("**Why We Recommend It:**")
                    st.markdown(f'<div class="why-box">{r.explanation}</div>', unsafe_allow_html=True)

        # Comparative Summary Card
        if result.summary:
            st.markdown(f"""
            <div class="summary-card">
                <h4 style="margin-top:0; color:#1565c0;">✨ Concierge Overview & Comparison</h4>
                <p style="font-size:1.05rem; line-height:1.6; margin-bottom:0;">{result.summary}</p>
            </div>
            """, unsafe_allow_html=True)

        # Execution Telemetry
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("⚡ Pipeline Performance & Telemetry"):
            col1, col2, col3, col4 = st.columns(4)
            timings = result.timings
            col1.metric("Total Latency", f"{timings.get('total_time_ms', 0)/1000:.2f} s")
            col2.metric("Filter Time", f"{timings.get('filter_time_ms', 0):.0f} ms")
            col3.metric("LLM Response Time", f"{timings.get('llm_time_ms', 0):.0f} ms")
            col4.metric("Candidates Screened", result.candidate_count)

else:
    # Initial landing guide
    st.info("👈 **Get Started:** Enter your location and preferences in the sidebar on the left, then click **Find Recommendations**.")

    col_tip1, col_tip2, col_tip3 = st.columns(3)
    with col_tip1:
        st.markdown("### 🎯 Real Dataset")
        st.write("Grounded directly in over 70,000 real restaurant records from the Zomato database.")
    with col_tip2:
        st.markdown("### 🤖 LLM Reasoning")
        st.write("Generates human-like, personalized justifications based on your exact mood and criteria.")
    with col_tip3:
        st.markdown("### ⚡ Zero Latency with Groq")
        st.write(f"Inference runs on ultra-fast Groq LPU hardware using `{LLM_MODEL}`.")
