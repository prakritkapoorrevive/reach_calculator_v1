import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Reach Calculator", layout="wide")
st.title("Reach Calculator")

# --- Load Data ---
@st.cache_data
def load_data():
    census = pd.read_csv("census_data_cleaned.csv")
    zip_df = pd.read_csv("zip_data_trimmed.csv")
    deals = pd.read_csv("deals_data_cleaned.csv")

    # Ensure zip formatting
    census["zip"] = census["zip"].astype(str).str.zfill(5)
    zip_df["zip"] = zip_df["zip"].astype(str).str.zfill(5)

    # Keep only ZIPs present in census
    uszips_census = zip_df.merge(
        census[["zip"]].drop_duplicates(), on="zip", how="inner"
    ).dropna(subset=["lat", "lng"])

    return census, zip_df, deals, uszips_census

census, zip_df, deals, uszips_census = load_data()

# --- Helper Functions ---
def haversine_mi(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1 = np.radians(lat1); lon1 = np.radians(lon1)
    lat2 = np.radians(lat2); lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def zips_within_radius_from_zip(origin_zip, radius_miles):
    origin_row = uszips_census.loc[uszips_census["zip"] == str(origin_zip).zfill(5)]
    if origin_row.empty:
        raise ValueError(f"Origin ZIP {origin_zip} not found.")
    lat0 = origin_row.iloc[0]["lat"]
    lon0 = origin_row.iloc[0]["lng"]

    dists = haversine_mi(lat0, lon0,
                         uszips_census["lat"].to_numpy(),
                         uszips_census["lng"].to_numpy())

    out = uszips_census.assign(distance_mi=dists)
    out = out.loc[out["distance_mi"] <= radius_miles] \
             .sort_values("distance_mi") \
             .reset_index(drop=True)

    return out

def get_age_bracket(age):
    if age < 18:
        return f"gender_Under 18"
    elif 18 <= age <= 24:
        return f"gender_18-24"
    elif 25 <= age <= 34:
        return f"gender_25-34"
    elif 35 <= age <= 44:
        return f"gender_35-44"
    elif 45 <= age <= 54:
        return f"gender_45-54"
    elif 55 <= age <= 64:
        return f"gender_55-64"
    else:
        return f"gender_65+"

# --- Main Calculation ---
def calculate_reach(deals_df, census_df, target_zips, target_gender=None, target_age=None, target_budget=None, aic_size=None, amazon_population_size=None):
    census_df["zip"] = census_df["zip"].astype(str).str.zfill(5)
    census_filtered = census_df[census_df["zip"].isin(target_zips)]

    if target_gender and target_age is not None:
        age_col = get_age_bracket(target_age).replace("gender", target_gender)
        pop_target = census_filtered[age_col].sum()
        pop_total = census_df[age_col].sum()
    elif target_gender:
        pop_target = census_filtered[f"{target_gender.capitalize()}_Total"].sum()
        pop_total = census_df[f"{target_gender.capitalize()}_Total"].sum()
    elif target_age is not None:
        age_col = get_age_bracket(target_age).replace("gender", "Total")
        pop_target = census_filtered[age_col].sum()
        pop_total = census_df[age_col].sum()
    else:
        pop_target = census_filtered["Total_Population"].sum()
        pop_total = census_df["Total_Population"].sum()

    pop_share = pop_target / pop_total

    if aic_size is not None and amazon_population_size is not None:
        aic_multiplier = aic_size / amazon_population_size
        pop_share *= aic_multiplier
    else:
        aic_multiplier = 1

    if target_gender:
        reach_col = f"nat_avail_reach_{target_gender.lower()}"
        imp_col = f"nat_avail_imp_{target_gender.lower()}"
        budget_col = f"nat_avail_budget_{target_gender.lower()}"
        if reach_col not in deals_df.columns: reach_col = "nat_avail_reach"
        if imp_col not in deals_df.columns: imp_col = "nat_avail_imp"
        if budget_col not in deals_df.columns: budget_col = "nat_avail_budget"
    else:
        reach_col = "nat_avail_reach"
        imp_col = "nat_avail_imp"
        budget_col = "nat_avail_budget"

    deals_df["est_reach"] = deals_df[reach_col] * pop_share
    deals_df["est_impressions"] = deals_df[imp_col] * pop_share
    deals_df["est_avail_budget"] = deals_df[budget_col] * pop_share

    if target_budget is not None:
        deals_df["budget_feasible"] = target_budget <= deals_df["est_avail_budget"]

    agg_result = deals_df[["deal", reach_col, imp_col, budget_col, "est_reach", "est_impressions", "est_avail_budget"]
                          + (["budget_feasible"] if target_budget is not None else [])]

    zip_results = []
    for _, zip_row in census_filtered.iterrows():
        if target_gender and target_age is not None:
            pop_target_zip = zip_row[get_age_bracket(target_age).replace("gender", target_gender)]
            pop_total_zip = pop_total
        elif target_gender:
            pop_target_zip = zip_row[f"{target_gender.capitalize()}_Total"]
            pop_total_zip = pop_total
        elif target_age is not None:
            pop_target_zip = zip_row[get_age_bracket(target_age).replace("gender", "Total")]
            pop_total_zip = pop_total
        else:
            pop_target_zip = zip_row["Total_Population"]
            pop_total_zip = pop_total

        pop_share_zip = pop_target_zip / pop_total_zip
        if aic_multiplier != 1:
            pop_share_zip *= aic_multiplier

        tmp_df = deals_df.copy()
        tmp_df["zip"] = zip_row["zip"]
        tmp_df["est_reach"] = tmp_df[reach_col] * pop_share_zip
        tmp_df["est_impressions"] = tmp_df[imp_col] * pop_share_zip
        tmp_df["est_avail_budget"] = tmp_df[budget_col] * pop_share_zip

        if target_budget is not None:
            tmp_df["budget_feasible"] = target_budget <= tmp_df["est_avail_budget"]

        zip_results.append(tmp_df[["zip", "deal", "est_reach", "est_impressions", "est_avail_budget"]
                                   + (["budget_feasible"] if target_budget is not None else [])])

    zip_result_df = pd.concat(zip_results, ignore_index=True)

    return agg_result, zip_result_df, pop_share

# --- Sidebar Inputs ---
st.sidebar.header("Inputs")
origin_zip = st.sidebar.text_input("Origin ZIP", "10001")
radius = st.sidebar.number_input("Radius (miles)", min_value=1, value=10)
target_gender = st.sidebar.selectbox("Target Gender", ["Male", "Female", "All"])
target_age = st.sidebar.number_input("Target Age", min_value=0, max_value=120, value=30)
campaign_budget = st.sidebar.number_input("Campaign Budget", min_value=0, value=10000)
aic_size = st.sidebar.number_input("AIC Size", min_value=1, value=25)
amazon_population_size = st.sidebar.number_input("Amazon Population Size", min_value=1, value=50)
run_btn = st.sidebar.button("Run Calculation")

# --- Run ---
if run_btn:
    try:
        nearby_census = zips_within_radius_from_zip(origin_zip, radius)
        target_zips = nearby_census["zip"].tolist()

        result_df, zip_result_df, share = calculate_reach(
            deals, census, target_zips, None if target_gender == "All" else target_gender,
            target_age, campaign_budget, aic_size=aic_size,
            amazon_population_size=amazon_population_size
        )

        st.success(f"Population share: {share:.2%}")

        tab1, tab2 = st.tabs(["Summary", "ZIP Details"])

        with tab1:
            st.subheader("Summary")
            st.dataframe(result_df)
            st.download_button("Download Summary CSV", result_df.to_csv(index=False), "summary.csv", "text/csv")

        with tab2:
            st.subheader("ZIP Details")
            st.dataframe(zip_result_df)
            st.download_button("Download ZIP Details CSV", zip_result_df.to_csv(index=False), "zip_details.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
