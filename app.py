import streamlit as st
import pandas as pd
import numpy as np

# ===== Load Data =====
@st.cache_data
def load_data():
    census = pd.read_csv("census_data_cleaned.csv")
    uszips = pd.read_csv("zip_data_trimmed.csv")
    deals = pd.read_csv("deals_data_cleaned.csv")

    # Keep ZIPs as 5-char strings
    census["zip"] = census["zip"].astype(str).str.zfill(5)
    uszips["zip"] = uszips["zip"].astype(str).str.zfill(5)

    # Only ZIPs present in census
    uszips_census = uszips.merge(
        census[["zip"]].drop_duplicates(), on="zip", how="inner"
    ).dropna(subset=["lat", "lng"])

    return census, uszips_census, deals

census_df, uszips_df, deals_df = load_data()

# ===== Distance Logic =====
def haversine_mi(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1 = np.radians(lat1); lon1 = np.radians(lon1)
    lat2 = np.radians(lat2); lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def zips_within_radius_from_zip(origin_zip, radius_miles):
    origin_row = uszips_df.loc[uszips_df["zip"] == str(origin_zip).zfill(5)]
    if origin_row.empty:
        st.error(f"Origin ZIP {origin_zip} not found.")
        return pd.DataFrame()
    lat0 = origin_row.iloc[0]["lat"]
    lon0 = origin_row.iloc[0]["lng"]

    dists = haversine_mi(lat0, lon0,
                         uszips_df["lat"].to_numpy(),
                         uszips_df["lng"].to_numpy())

    out = uszips_df.assign(distance_mi=dists)
    out = out.loc[out["distance_mi"] <= radius_miles]              .sort_values("distance_mi")              .reset_index(drop=True)

    return out[["zip", "city", "state_id", "distance_mi"]]

# ===== Age Bracket Mapping =====
def get_age_bracket(age):
    if age < 18:
        return "Under 18"
    elif 18 <= age <= 24:
        return "18-24"
    elif 25 <= age <= 34:
        return "25-34"
    elif 35 <= age <= 44:
        return "35-44"
    elif 45 <= age <= 54:
        return "45-54"
    elif 55 <= age <= 64:
        return "55-64"
    else:
        return "65+"

# ===== Streamlit UI =====
st.title("ZIP Finder & Reach Calculator")

st.sidebar.header("User Inputs")
origin_zip = st.sidebar.text_input("Origin ZIP Code", value="10001")
radius = st.sidebar.number_input("Radius (miles)", value=10, step=1)
target_gender = st.sidebar.selectbox("Target Gender", ["All", "Male", "Female"])
target_age = st.sidebar.number_input("Target Age", value=30, min_value=0, max_value=120)
target_budget = st.sidebar.number_input("Target Budget (USD)", value=0)
selected_deal = st.sidebar.selectbox("Select Deal (optional)", ["None"] + deals_df["deal"].tolist())

if st.sidebar.button("Run Search"):
    # Get nearby ZIPs
    nearby = zips_within_radius_from_zip(origin_zip, radius)
    if not nearby.empty:
        # Merge with census data
        merged = nearby.merge(census_df, on="zip", how="left")

        # Apply gender filter
        if target_gender != "All":
            pop_col = f"{target_gender.capitalize()}_Total"
            merged = merged.assign(Target_Population=merged[pop_col])
        else:
            merged = merged.assign(Target_Population=merged["Total_Population"])

        # Apply age filter
        if target_age > 0:
            bracket = get_age_bracket(target_age)
            age_col = f"Total_{bracket}" if target_gender == "All" else f"{target_gender.capitalize()}_{bracket}"
            merged = merged.assign(Target_Population=merged[age_col])

        # Deal/budget calculations
        if selected_deal != "None" and target_budget > 0:
            deal_row = deals_df.loc[deals_df["deal"] == selected_deal].iloc[0]
            nat_reach = deal_row["nat_avail_reach"]
            nat_budget = deal_row["nat_avail_budget"]

            merged["Reach_Estimate"] = (merged["Target_Population"] / census_df["Total_Population"].sum()) * nat_reach
            merged["Budget_Required"] = (merged["Reach_Estimate"] / nat_reach) * nat_budget

        st.subheader("Results")
        st.dataframe(merged)

        # Download button
        csv = merged.to_csv(index=False)
        st.download_button("Download CSV", csv, "zip_finder_results.csv", "text/csv")

    else:
        st.warning("No ZIPs found in that radius.")
