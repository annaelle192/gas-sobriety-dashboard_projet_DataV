"""
Energy sobriety: has France really cut its gas consumption?
Individual Streamlit project — EFREI 2026 — #EFREIDataStories2026

Run:   streamlit run app.py
Data:  tables built by etape2_preparation.ipynb (same folder as this file).
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FOLDER = Path(__file__).resolve().parent
REFERENCE = (2018, 2021)          # pre-crisis reference period
SOURCE = ("Source: Consommation quotidienne brute régionale & nationale — NaTran, Teréga, RTE "
          "via ODRÉ — data.gouv.fr — Licence Ouverte / Open Licence 2.0")
GEOJSON_URL = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/"
               "regions-version-simplifiee.geojson")

# Colours (colour-blind-safe palette): one colour per energy, grey for the reference
COLOURS = {"Gas": "#2a78d6", "Electricity": "#eb6834"}
GREY = "#8a8985"
GREY_BAND = "rgba(138, 137, 133, 0.22)"
ENERGIES = {"Gas": "gaz_gwh", "Electricity": "elec_gwh"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# The prepared tables are in French: labels translated for display
STATUS_EN = {"Définitif": "Final", "Redressé": "Corrected by producer", "Consolidé": "Consolidated",
             "Intermédiaire": "Interim", "Meilleur Statut": "Best available"}
SOURCE_EN = {"Gaz NaTran": "Gas – NaTran", "Gaz Teréga": "Gas – Teréga", "Électricité RTE": "Electricity – RTE"}
LOG_EN = [  # (French fragment, English), applied in order
    ("Lecture du fichier régional", "Read regional file"),
    ("Lecture du fichier national", "Read national file"),
    ("Heures fantômes supprimées", "Phantom hours removed (spring DST change)"),
    ("Doublons restants supprimés", "Remaining duplicates removed"),
    ("Doublons restants", "Remaining duplicates"),
    ("Électricité négative remplacée par une valeur manquante", "Negative electricity value set to missing"),
    ("Statut invalide remplacé", "Invalid status set to missing"),
    ("Colonne flag_ignore supprimée (toujours « non »)", "Column flag_ignore dropped (always 'non')"),
    ("Journées région incomplètes (signalées, non supprimées)", "Incomplete region-days (flagged, kept)"),
    ("Jours avec un écart > 1 %", "Days with a regional/national gap > 1%"),
    ("(régional", "(regional"), ("(national", "(national"),
    ("jours concernés", "days affected"), ("valeurs", "values"), ("journées région", "region-days"),
    ("écart médian", "median gap"), ("sur ", "out of "),
]

st.set_page_config(page_title="Gas sobriety — data storytelling", page_icon="🔥", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached: read once)
# ---------------------------------------------------------------------------
FILES = ["conso_jour_region.csv", "profil_horaire.csv", "qualite_statuts.csv",
         "qualite_validation.csv", "journal_nettoyage.csv"]
missing = [f for f in FILES if not (FOLDER / f).exists()]
if missing:
    st.error(f"File(s) not found in {FOLDER}: **{', '.join(missing)}**.\n\n"
             "Run etape2_preparation.ipynb in this same folder (Kernel → Restart & Run All): "
             "it creates these files next to app.py.")
    st.stop()


def translate_log(text):
    text = str(text)
    for fr, en in LOG_EN:
        text = text.replace(fr, en)
    return text


@st.cache_data(show_spinner="Loading data…")
def load_data():
    daily = pd.read_csv(FOLDER / "conso_jour_region.csv", parse_dates=["jour"])
    hourly = pd.read_csv(FOLDER / "profil_horaire.csv")
    status = pd.read_csv(FOLDER / "qualite_statuts.csv")
    validation = pd.read_csv(FOLDER / "qualite_validation.csv", parse_dates=["jour"])
    log = pd.read_csv(FOLDER / "journal_nettoyage.csv")
    # If a notebook cell was re-run on its own, the same step can appear twice
    log = log.drop_duplicates(subset="etape", keep="first").fillna("")
    log["etape"] = log["etape"].map(translate_log)
    log["detail"] = log["detail"].map(translate_log)
    status["statut"] = status["statut"].map(lambda s: STATUS_EN.get(s, s))
    status["source"] = status["source"].map(lambda s: SOURCE_EN.get(s, s))
    return daily, hourly, status, validation, log


@st.cache_data(show_spinner=False)
def load_regions_geojson():
    """Region outlines: local file, otherwise downloaded once."""
    path = FOLDER / "regions.geojson"
    try:
        if not path.exists():
            path.write_text(requests.get(GEOJSON_URL, timeout=30).text, encoding="utf-8")
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Calculations and helpers
# ---------------------------------------------------------------------------
def complete_years(daily):
    """Years with every day present (2026 stops at the end of August)."""
    n_days = daily.groupby("annee")["jour"].nunique()
    expected = pd.Series({y: 366 if pd.Timestamp(y, 12, 31).dayofyear == 366 else 365 for y in n_days.index})
    return sorted(n_days[n_days == expected].index)


def yearly_total(df, column):
    """Yearly consumption in TWh."""
    return df.groupby("annee")[column].sum() / 1000


def change_vs_reference(df, column, year):
    """Change (%) of the selected year vs the 2018-2021 average, over the same months.

    An incomplete year (2026) is compared with the same months of the reference period.
    Returns (change in %, consumption of the year in TWh, months compared).
    """
    months = sorted(df.loc[df["annee"] == year, "mois"].unique())
    same_months = df[df["mois"].isin(months)]
    current = same_months.loc[same_months["annee"] == year, column].sum() / 1000
    ref = same_months[same_months["annee"].between(*REFERENCE)].groupby("annee")[column].sum().mean() / 1000
    return 100 * (current / ref - 1), current, months


def months_label(months):
    return "full year" if len(months) == 12 else f"{MONTHS[months[0] - 1]}–{MONTHS[months[-1] - 1]}"


def num(x, dec=0):
    return f"{x:,.{dec}f}"


def pct(x, dec=1):
    """Signed percentage, e.g. -26.9%."""
    return f"{x:+.{dec}f}%"


def style(fig, y_title, height=420):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title=y_title, hovermode="x unified", legend_title_text="")
    return fig


def alt_text(text):
    """Text description of the chart (accessibility)."""
    st.caption(f"Chart description: {text}")


# ---------------------------------------------------------------------------
# Load + sidebar filters
# ---------------------------------------------------------------------------
daily, hourly, status, validation, log = load_data()
COMPLETE = complete_years(daily)
ALL_REGIONS = sorted(daily["region"].unique())

with st.sidebar:
    st.header("Filters")
    energy = st.radio("Energy", list(ENERGIES), horizontal=True,
                      help="Gas: transmission network (NaTran, Teréga). Electricity: RTE network.")
    all_regions = st.toggle("All regions", value=True, help="Mainland France, excluding Corsica.")
    regions = ALL_REGIONS if all_regions else st.multiselect("Regions", ALL_REGIONS, default=["Île-de-France"])
    year_min, year_max = int(daily["annee"].min()), int(daily["annee"].max())
    period = st.slider("Years shown", year_min, year_max, (max(year_min, 2014), year_max),
                       help="2013 is hidden by default: its split between regions is atypical "
                            "(see 'Data quality').")
    year_choices = list(range(year_max, REFERENCE[1], -1))
    default_year = max(COMPLETE) if max(COMPLETE) in year_choices else year_choices[0]
    year = st.selectbox("Year studied (vs 2018–2021)", year_choices, index=year_choices.index(default_year),
                        help="An incomplete year is compared with the same months of 2018–2021.")
    exclude = st.toggle("Exclude incomplete days", value=True,
                        help="Days where an hour of gas or a half-hour of electricity is missing.")
    st.divider()
    st.caption(f"Pre-crisis reference: {REFERENCE[0]}–{REFERENCE[1]} average.")
    st.caption(SOURCE)

if not regions:
    st.warning("Select at least one region in the sidebar.")
    st.stop()

column = ENERGIES[energy]
colour = COLOURS[energy]
data = daily[daily["region"].isin(regions)]
if exclude:
    data = data[data["complet"]]
view = data[data["annee"].between(*period)]
change, consumption, months_studied = change_vs_reference(data, column, year)
scope = "mainland France excl. Corsica" if len(regions) == len(ALL_REGIONS) else f"{len(regions)} region(s)"


# ---------------------------------------------------------------------------
# 0. Introduction
# ---------------------------------------------------------------------------
st.title("Energy sobriety: has France really cut its gas consumption?")
st.caption(SOURCE)

st.markdown(
    """
In autumn 2022, the war in Ukraine sent gas prices soaring and threatened Europe's supply. The French
government launched an **energy sobriety plan** with a target of **−10%** energy consumption within two years.
Four years later, what do the meters say?

This dashboard uses **13 years of hourly measurements** (2013–2026) from the gas and electricity networks,
for each of the 12 regions of mainland France.

- **Question:** is the drop in gas consumption real, lasting, and where is it strongest?
- **Audience:** the general public, local authorities and decision-makers following the energy transition.
- **How to read it:** each section opens with a sentence in bold summarising the key insight.
  The filters on the left (energy, regions, years, year studied) update every chart.
"""
)
with st.expander("What this data measures (and what it does not)"):
    st.markdown(
        """
- **Raw consumption:** it is not weather-corrected. A mild winter lowers consumption without any sobriety effort.
- **Gas** is measured on the **transmission network**. It supplies households and businesses (through the
  distribution networks), but also **large industrial sites** and **gas-fired power plants**.
  Biomethane injected directly into distribution networks is not counted.
- **Units:** measurements are power values (MW), converted into energy: 1 TWh = 1,000 GWh = 1 million MWh.
  Gas values use the gross calorific value (GCV / PCS).
"""
    )

# ---------------------------------------------------------------------------
# 1. Key figures
# ---------------------------------------------------------------------------
st.header("At a glance")
yearly = yearly_total(data, column)
yearly_shown = yearly[yearly.index.isin(COMPLETE) & yearly.index.isin(range(period[0], period[1] + 1))]
reference = yearly[yearly.index.isin(range(REFERENCE[0], REFERENCE[1] + 1))].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{energy}: 2018–2021 average", f"{num(reference)} TWh/yr", help=f"Scope: {scope}.")
c2.metric(f"{energy} in {year}", f"{num(consumption)} TWh", delta=f"{pct(change)} vs 2018–2021",
          delta_color="inverse", help=f"Months compared: {months_label(months_studied)}.")
if len(yearly_shown):
    c3.metric(f"Lowest ({yearly_shown.idxmin()})", f"{num(yearly_shown.min())} TWh",
              help="Lowest full year in the years shown.")
    c4.metric(f"Highest ({yearly_shown.idxmax()})", f"{num(yearly_shown.max())} TWh",
              help="Highest full year in the years shown.")
st.caption(f"Scope: {scope}. A drop is shown in green: that is the aim of the sobriety plan.")

# ---------------------------------------------------------------------------
# 2. Before / after
# ---------------------------------------------------------------------------
st.header("Before / after: the 2022 break")
change_2014 = 100 * (yearly.get(2014, float("nan")) / reference - 1)
st.markdown(
    f"**In {year}, {energy.lower()} consumption is {abs(change):.1f}% "
    f"{'below' if change < 0 else 'above'} the 2018–2021 average.** "
    + (f"For comparison, the very mild winter of 2014 cut consumption by {abs(change_2014):.1f}%, "
       "but that drop vanished the following year." if energy == "Gas" and change_2014 < 0 else "")
)

bars = yearly_shown.reset_index(name="twh")
bars["gap"] = 100 * (bars["twh"] / reference - 1)
fig = go.Figure(go.Bar(
    x=bars["annee"], y=bars["twh"], marker_color=colour, name=energy, customdata=bars["gap"],
    hovertemplate="%{x}: %{y:,.1f} TWh<br>%{customdata:+.1f}% vs 2018–2021<extra></extra>"))
fig.add_hline(y=reference, line_dash="dash", line_color=GREY,
              annotation_text=f"2018–2021 average: {num(reference)} TWh", annotation_position="top right")
for y_note, note in [(2014, "Very mild winter"), (2022, "War in Ukraine,<br>sobriety plan")]:
    if y_note in bars["annee"].values:
        fig.add_annotation(x=y_note, y=bars.loc[bars["annee"] == y_note, "twh"].iloc[0], text=note,
                           showarrow=True, arrowhead=0, ay=-45, font=dict(size=12))
fig.update_xaxes(title="Year", dtick=1)
st.plotly_chart(style(fig, "Yearly consumption (TWh)"), use_container_width=True)
alt_text(f"bars of yearly {energy.lower()} consumption (full years) against the 2018–2021 average "
         "(dashed line), annotated for the mild winter of 2014 and the 2022 crisis.")

# ---------------------------------------------------------------------------
# 3. Month by month
# ---------------------------------------------------------------------------
st.header("Month by month: is the drop concentrated in winter?")
monthly = data.groupby(["annee", "mois"])[column].sum().div(1000).reset_index(name="twh")
ref_month = (monthly[monthly["annee"].between(*REFERENCE)].groupby("mois")["twh"]
             .agg(["mean", "min", "max"]).reindex(range(1, 13)))
year_month = monthly[monthly["annee"] == year].set_index("mois")["twh"]


def gap_over(months):
    """Gap with 2018-2021 over these months: (in %, in TWh)."""
    m = [x for x in months if x in year_month.index]
    if not m:
        return float("nan"), float("nan")
    current, ref = year_month[m].sum(), ref_month.loc[m, "mean"].sum()
    return 100 * (current / ref - 1), current - ref


(p_winter, t_winter), (p_rest, t_rest) = gap_over([1, 2, 3, 10, 11, 12]), gap_over([4, 5, 6, 7, 8, 9])
st.markdown(
    f"**In {year}, the gap with 2018–2021 is {t_winter:+,.0f} TWh ({pct(p_winter)}) during the heating months "
    f"(October to March) and {t_rest:+,.0f} TWh ({pct(p_rest)}) the rest of the year.**"
    + (" In volume, most of the drop happens in winter; but in proportion it is even stronger outside the heating "
       "season. Heating does not explain everything: industry and gas-fired power plants matter too."
       if energy == "Gas" and t_winter < t_rest < 0 and p_rest < p_winter else "")
)

fig = go.Figure()
fig.add_trace(go.Scatter(x=MONTHS, y=ref_month["max"], mode="lines", line=dict(width=0), hoverinfo="skip",
                         showlegend=False))
fig.add_trace(go.Scatter(x=MONTHS, y=ref_month["min"], mode="lines", fill="tonexty", fillcolor=GREY_BAND,
                         line=dict(width=0), name="2018–2021 range (min–max)", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=MONTHS, y=ref_month["mean"], name="2018–2021 average", mode="lines",
                         line=dict(color=GREY, dash="dash", width=2), hovertemplate="%{y:,.1f} TWh"))
fig.add_trace(go.Scatter(x=[MONTHS[m - 1] for m in year_month.index], y=year_month.values, name=str(year),
                         mode="lines+markers", line=dict(color=colour, width=3), marker=dict(size=8),
                         hovertemplate="%{y:,.1f} TWh"))
fig.update_xaxes(title="Month")
st.plotly_chart(style(fig, "Monthly consumption (TWh)"), use_container_width=True)
alt_text(f"line of monthly {energy.lower()} consumption in {year}, compared with the 2018–2021 average "
         "(dashed) and its minimum–maximum range (grey band).")

# ---------------------------------------------------------------------------
# 4. Regions
# ---------------------------------------------------------------------------
st.header("Regions: where is the drop strongest?")
by_region = []
for r in regions:
    e, c, _ = change_vs_reference(data[data["region"] == r], column, year)
    code = data.loc[data["region"] == r, "code_region"].iloc[0]
    by_region.append({"region": r, "code": str(int(code)), "change": e, "twh": c})
by_region = pd.DataFrame(by_region).sort_values("change")

if len(by_region) > 1:
    first, last = by_region.iloc[0], by_region.iloc[-1]
    st.markdown(f"**In {year}, the largest drop is in {first['region']} ({pct(first['change'])}); "
                + (f"the smallest is in {last['region']} ({pct(last['change'])}).**" if last["change"] < 0
                   else f"{last['region']} is up ({pct(last['change'])}).**"))

left, right = st.columns([3, 2])
outlines = load_regions_geojson()
bound = max(5, by_region["change"].abs().max())
with left:
    if outlines:
        fig = px.choropleth_mapbox(by_region, geojson=outlines, locations="code", featureidkey="properties.code",
                                   color="change", hover_name="region", color_continuous_scale="RdBu_r",
                                   range_color=(-bound, bound), mapbox_style="white-bg",
                                   center={"lat": 46.6, "lon": 2.4}, zoom=4.2, opacity=0.9,
                                   hover_data={"code": False, "change": ":.1f", "twh": ":.1f"},
                                   labels={"change": "Change (%)", "twh": f"TWh in {year}"})
        fig.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=0),
                          coloraxis_colorbar=dict(title="% vs<br>2018–2021"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Map outlines unavailable: see the ranking on the right.")
with right:
    fig = go.Figure(go.Bar(x=by_region["change"], y=by_region["region"], orientation="h",
                           marker_color=colour, hovertemplate="%{y}: %{x:+.1f}%<extra></extra>"))
    fig.update_xaxes(title="Change vs 2018–2021 (%)", zeroline=True, zerolinecolor=GREY)
    st.plotly_chart(style(fig, "", height=460).update_layout(hovermode="closest"), use_container_width=True)
alt_text(f"map and ranking of regions by the change in their {energy.lower()} consumption in {year} "
         "compared with 2018–2021. Blue: decrease; red: increase.")
if energy == "Gas" and "Bretagne" in regions:
    st.info("**Why does Brittany (Bretagne) fall less?** A likely explanation: the Landivisiau gas-fired power "
            "plant (Finistère, 400 MW) entered commercial service on 31 March 2022, after test runs in winter "
            "2021–2022. It adds new gas demand in the region, which also explains the 2022 peak. It is a reminder "
            "that this data mixes heating, industry and electricity generation.")

st.subheader("Year by year, region by region")
st.markdown("Index 100 = each region's own 2018–2021 average: we compare trends, not volumes.")
reg_year = view[view["annee"].isin(COMPLETE)].groupby(["region", "annee"])[column].sum().reset_index()
ref_reg = reg_year[reg_year["annee"].between(*REFERENCE)].groupby("region")[column].mean().rename("ref")
reg_year = reg_year.join(ref_reg, on="region")
reg_year["index"] = 100 * reg_year[column] / reg_year["ref"]
fig = px.line(reg_year, x="annee", y="index", facet_col="region", facet_col_wrap=4,
              color_discrete_sequence=[colour], labels={"annee": "Year", "index": "Index"},
              hover_data={"index": ":.0f"}, height=620)
fig.add_hline(y=100, line_dash="dot", line_color=GREY)
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig, use_container_width=True)
alt_text("small multiples, one per region, showing yearly consumption as an index (100 = 2018–2021 average). "
         "The dotted line marks the reference level.")

# ---------------------------------------------------------------------------
# 5. Hourly profile
# ---------------------------------------------------------------------------
st.header("Through the day: when is energy used?")
season = st.radio("Season", ["Winter (December to February)", "Summer (June to August)"], horizontal=True)
season_months = [12, 1, 2] if season.startswith("Winter") else [6, 7, 8]
col_mw = "gaz_mw" if energy == "Gas" else "elec_mw"
prof = hourly[hourly["region"].isin(regions) & hourly["mois"].isin(season_months)]
prof = prof.groupby(["annee", "mois", "heure"])[col_mw].sum().reset_index()      # sum of regions
prof = prof.groupby(["annee", "heure"])[col_mw].mean().reset_index()             # average of months
prof_ref = prof[prof["annee"].between(*REFERENCE)].groupby("heure")[col_mw].mean()
prof_year = prof[prof["annee"] == year].set_index("heure")[col_mw]

if len(prof_year):
    gap_h = 100 * (prof_year / prof_ref - 1)
    st.markdown(f"**{season.split(' (')[0]} {year}: average power drawn is {pct(gap_h.mean())} vs 2018–2021, "
                f"between {pct(gap_h.min())} and {pct(gap_h.max())} depending on the hour. "
                "The daily shape (morning and evening peaks) is unchanged.**")
fig = go.Figure()
fig.add_trace(go.Scatter(x=prof_ref.index, y=prof_ref.values, name="2018–2021 average",
                         line=dict(color=GREY, dash="dash", width=2), hovertemplate="%{y:,.0f} MW"))
fig.add_trace(go.Scatter(x=prof_year.index, y=prof_year.values, name=str(year),
                         line=dict(color=colour, width=3), hovertemplate="%{y:,.0f} MW"))
fig.update_xaxes(title="Hour (local time)", dtick=2, ticksuffix=":00")
fig.update_yaxes(tickformat=",.0f")
st.plotly_chart(style(fig, "Average power drawn (MW)"), use_container_width=True)
alt_text(f"line of average {energy.lower()} power hour by hour in {season.lower()}, "
         f"in {year} and on average over 2018–2021.")

# ---------------------------------------------------------------------------
# 6. Gas vs electricity
# ---------------------------------------------------------------------------
st.header("Was gas replaced by electricity?")
base = data[data["annee"].isin(COMPLETE) & data["annee"].between(*period)]
indices = []
for name, c in ENERGIES.items():
    t = yearly_total(base, c)
    ref_c = yearly_total(data, c).loc[REFERENCE[0]:REFERENCE[1]].mean()
    indices.append(pd.DataFrame({"annee": t.index, "index": 100 * t.values / ref_c, "energy": name}))
indices = pd.concat(indices)
last_year = indices["annee"].max()
end = indices[indices["annee"] == last_year].set_index("energy")["index"]
if {"Gas", "Electricity"} <= set(end.index):
    st.markdown(f"**In {last_year}, gas stands at index {end['Gas']:.0f} and electricity at "
                f"{end['Electricity']:.0f} (100 = 2018–2021): "
                + ("both have fallen, so the drop in gas was not offset by electricity.**"
                   if end["Electricity"] < 100 else "electricity is up while gas is down.**"))
fig = px.line(indices, x="annee", y="index", color="energy", color_discrete_map=COLOURS, markers=True,
              labels={"annee": "Year", "index": "Index (100 = 2018–2021 average)", "energy": ""})
fig.add_hline(y=100, line_dash="dot", line_color=GREY)
for name in end.index:   # direct label at the end of each line
    fig.add_annotation(x=last_year, y=end[name], text=f" {name}", showarrow=False, xanchor="left",
                       font=dict(color=COLOURS[name]))
fig.update_traces(hovertemplate="%{y:.0f}")
fig.update_xaxes(dtick=1)
st.plotly_chart(style(fig, "Index (100 = 2018–2021 average)"), use_container_width=True)
alt_text("two lines, gas and electricity, as an index (100 = 2018–2021 average), to compare their trends "
         "on the same scale.")

with st.expander("Show yearly data (table)"):
    table = indices.pivot(index="annee", columns="energy", values="index").round(1)
    table.columns = [f"{c} index" for c in table.columns]
    st.dataframe(table.rename_axis("Year"), use_container_width=True)

# ---------------------------------------------------------------------------
# 7. Data quality
# ---------------------------------------------------------------------------
st.header("Data quality and limitations")
complete_share = daily["complet"].mean() * 100
median_gap = validation["ecart_gaz_pct"].median()
q1, q2, q3 = st.columns(3)
q1.metric("Complete region-days", f"{complete_share:.2f}%",
          help="Every hour of gas and half-hour of electricity is filled in.")
q2.metric("Median gap regions vs national (gas)", f"{median_gap:.2f}%",
          help="Sum of the 12 regions compared with the national file, day by day.")
q3.metric("Steps in the cleaning log", f"{len(log)}", help="Details in the log below.")

st.markdown(
    """
**Checks performed (see notebooks `etape1_donnees` and `etape2_preparation`):**
- **Missing values:** gas is measured every hour and electricity every half-hour, so 50% of rows without gas
  is expected. On full hours, less than 0.01% of gas values are missing. Teréga only operates in 3 regions
  (Nouvelle-Aquitaine, Occitanie, Auvergne-Rhône-Alpes).
- **Duplicates:** when clocks go forward (end of March), the file contains "02:00" and "02:30" rows for an hour
  that does not exist. They are removed (336 rows over 14 days).
- **Outliers:** one negative electricity value and one invalid status, set to missing.
- **Consistency:** the sum of the regions matches the national total (median gap of zero). A few periods
  diverge, which suggests perimeter differences between the two files: the analysis relies on the regional file.
- **Atypical 2013:** in early 2013 the sum of the regions is about 15% below the national total, and the split
  between regions is unusual (Île-de-France very low, Occitanie and Centre-Val de Loire very high). The year is
  hidden by default and is not part of the 2018–2021 reference.
"""
)
tab1, tab2, tab3 = st.tabs(["Cleaning log", "Data status", "Regions vs national gap"])
with tab1:
    st.dataframe(log.rename(columns={"etape": "Step", "lignes_concernees": "Rows affected", "detail": "Detail"}),
                 use_container_width=True, hide_index=True)
with tab2:
    source_q = st.selectbox("Source", status["source"].unique())
    s = status[status["source"] == source_q]
    order = [x for x in STATUS_EN.values() if x in s["statut"].unique()]
    fig = px.bar(s, x="annee", y="pct", color="statut", category_orders={"statut": order},
                 color_discrete_sequence=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
                 labels={"annee": "Year", "pct": "Share of values (%)", "statut": "Status"})
    fig.update_traces(hovertemplate="%{x}: %{y:.1f}%")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(style(fig, "Share of values (%)", 360), use_container_width=True)
    alt_text("stacked bars of the share of values by status and year. 'Corrected by producer': values revised "
             "by the network operator (gas, 2022); 'Consolidated': recent values that may still change.")
with tab3:
    fig = go.Figure(go.Scatter(x=validation["jour"], y=validation["ecart_gaz_pct"].clip(-20, 20), mode="lines",
                               line=dict(color=COLOURS["Gas"], width=1), name="Gas",
                               hovertemplate="%{x|%d %b %Y}: %{y:.2f}%<extra></extra>"))
    fig.add_hrect(y0=-1, y1=1, fillcolor=GREY_BAND, line_width=0, annotation_text="± 1%",
                  annotation_position="top left")
    fig.update_xaxes(title="Date")
    st.plotly_chart(style(fig, "Gap regions vs national (%)", 360).update_layout(hovermode="closest"),
                    use_container_width=True)
    alt_text("daily gap (%) between the sum of the regions and the national total for gas, capped at ±20%. "
             "The grey band marks ±1%.")

st.markdown(
    """
**Limitations to keep in mind:**
- **Weather:** the data is not temperature-corrected; part of the drop may come from milder winters.
- **Mixed causes:** gas on the transmission network combines household sobriety, lower industrial demand and
  changes in gas-fired power generation. This data cannot separate these effects.
- **Revisable data:** recent electricity values are "consolidated" (not final yet), and 2022 gas data was
  corrected by the network operator.
- **2026 is incomplete** (up to 31 August): it is always compared with the same months of 2018–2021.
"""
)

# ---------------------------------------------------------------------------
# 8. Key takeaways (always about gas, the subject of the story)
# ---------------------------------------------------------------------------
st.header("Key takeaways")
gas_change, _, gas_months = change_vs_reference(data, "gaz_gwh", year)
elec_change, _, _ = change_vs_reference(data, "elec_gwh", year)
gas_yearly = yearly_total(data, "gaz_gwh")
gas_ref = gas_yearly.loc[REFERENCE[0]:REFERENCE[1]].mean()
post = [y for y in COMPLETE if y >= 2023]
post_changes = 100 * (gas_yearly.loc[post] / gas_ref - 1) if post else pd.Series(dtype=float)
reg_changes = pd.Series({r: change_vs_reference(data[data["region"] == r], "gaz_gwh", year)[0] for r in regions})
risers = reg_changes[reg_changes >= 0].sort_values(ascending=False)
fallers = reg_changes[reg_changes < 0]

# 1. Size and durability of the drop
if gas_change <= -10:
    target = "That goes beyond the −10% target of the sobriety plan."
elif gas_change < 0:
    target = "That is a drop, but short of the −10% target" + (
        " (the plan only started in October 2022)." if year == 2022 else ".")
else:
    target = "There is no drop compared with the pre-crisis level."
lasting = (f" Every full year since 2023 has stayed below the reference (between {pct(post_changes.min())} and "
           f"{pct(post_changes.max())}), whereas the 2014 mild-winter dip disappeared the following year."
           if len(post_changes) and post_changes.max() < 0 else "")
point1 = (f"**1. {'A real drop.' if gas_change < 0 else 'No drop.'}** In {year}, gas consumption is "
          f"{pct(gas_change)} vs 2018–2021 ({months_label(gas_months)}, {scope}). {target}{lasting}")

# 2. Electricity
point2 = (f"**2. Gas was not replaced by electricity:** electricity also fell ({pct(elec_change)}) over the same months."
          if elec_change < 0 else
          f"**2. Electricity rose ({pct(elec_change)}) while gas fell:** some switching to electricity is possible.")

# 3. Regions
if len(regions) == 1:
    point3 = f"**3. In {regions[0]},** gas consumption is {pct(reg_changes.iloc[0])} vs 2018–2021."
elif risers.empty:
    point3 = (f"**3. All {len(regions)} selected regions are down,** from {pct(fallers.min())} to "
              f"{pct(fallers.max())}: the map shows where the drop is strongest.")
else:
    up = ", ".join(f"{r} ({pct(v)})" for r, v in risers.items())
    point3 = (f"**3. {len(fallers)} of {len(regions)} regions are down** "
              + (f"({pct(fallers.min())} to {pct(fallers.max())}); " if len(fallers) else "; ")
              + f"up: {up}."
              + (" In Brittany, this is likely due to the new Landivisiau gas-fired power plant (2022)."
                 if "Bretagne" in risers.index else ""))

st.success("\n\n".join([point1, point2, point3]))
st.info(
    """
**Next steps:**
- Weather-correct consumption (heating degree days) to isolate the share due to sobriety.
- Separate households, industry and power plants using distribution-network data.
- Follow winter 2026–2027 to check whether the drop holds as prices come down.
"""
)
st.caption(SOURCE + " — Map outlines: france-geojson (simplified region boundaries).")
