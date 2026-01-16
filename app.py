import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np

app = FastAPI(title="Equal Property AI - Leasing Momentum Analytics")

from dotenv import load_dotenv
import os

from urllib.parse import quote_plus

from sqlalchemy import create_engine

import pandas as pd

load_dotenv()

DB_HOST = os.getenv("DB_HOST")

DB_PORT = os.getenv("DB_PORT")

DB_NAME = os.getenv("DB_NAME")

DB_USER = os.getenv("DB_USER")

DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DATABASE_URL = (

f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"

f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"

)

engine = create_engine(DATABASE_URL)

engine = create_engine(DATABASE_URL)

# ---------------- MODELS ----------------
class MonthlyMetric(BaseModel):
    month: str
    total_units: int
    leased_units: int
    vacant_units: int
    physical_occupancy: float
    monthly_revenue: float

class LeasingMomentumResponse(BaseModel):
    property_id: int
    property_name: str
    momentum_status: str
    rolling_6m_occupancy: float
    early_warning_flags: List[str]
    performance_data: List[MonthlyMetric]

class RevenueTrendResponse(BaseModel):
    property_id: int
    property_name: str
    month: str
    rolling_12m_revenue: float

class DecliningAssetResponse(BaseModel):
    property_id: int
    property_name: str
    decline_months: int

# # ---------------- CORE QUERY ----------------
BASE_QUERY = text("""
    SELECT 
        p.ID AS PropertyID,
        p.NAME AS PropertyName,
        c.START_DATE,
        c.END_DATE,
        cu.UNIT_ID,
        cc.TOTAL_AMOUNT AS ChargeAmount,
        (SELECT COUNT(*) 
         FROM TERP_LS_PROPERTY_UNIT pu 
         WHERE pu.PROPERTY_ID = p.ID) AS TotalUnits
    FROM TERP_LS_PROPERTY p
    LEFT JOIN TERP_LS_CONTRACT c ON p.ID = c.PROPERTY_ID
    LEFT JOIN TERP_LS_CONTRACT_UNIT cu ON c.ID = cu.CONTRACT_ID
    LEFT JOIN TERP_LS_CONTRACT_CHARGES cc ON c.ID = cc.CONTRACT_ID
    WHERE c.END_DATE >= DATE_SUB(CURRENT_DATE, INTERVAL 24 MONTH)
       OR c.ID IS NULL
""")

# # ---------------- 1️⃣ LEASING MOMENTUM + VACANT UNITS ----------------
# @app.get("/api/v1/leasing/momentum", response_model=List[LeasingMomentumResponse])
# def leasing_momentum(property_id: Optional[int] = None):

#     with engine.connect() as conn:
#         df = pd.read_sql(BASE_QUERY, conn)

#     if df.empty:
#         return []

#     months = pd.date_range(end=pd.Timestamp.today(), periods=24, freq="MS")

#     results = []

#     for pid, grp in df.groupby("PropertyID"):
#         if property_id and pid != property_id:
#             continue

#         pname = grp["PropertyName"].iloc[0]
#         total_units = int(grp["TotalUnits"].iloc[0])
#         metrics = []

#         for m in months:
#             active = grp[
#                 (pd.to_datetime(grp["START_DATE"]) <= m) &
#                 (pd.to_datetime(grp["END_DATE"]) >= m)
#             ]

#             leased = active["UNIT_ID"].nunique()
#             vacant = total_units - leased
#             revenue = active["ChargeAmount"].sum()

#             metrics.append({
#                 "month": m.strftime("%Y-%m"),
#                 "total_units": total_units,
#                 "leased_units": leased,
#                 "vacant_units": vacant,
#                 "physical_occupancy": round((leased / total_units) * 100, 2) if total_units else 0,
#                 "monthly_revenue": float(revenue)
#             })

#         dfm = pd.DataFrame(metrics)

#         rolling_6m = dfm["physical_occupancy"].rolling(6).mean().iloc[-1]
#         latest = dfm["physical_occupancy"].iloc[-1]

#         if latest > rolling_6m + 1:
#             status = "Improving"
#         elif latest < rolling_6m - 1:
#             status = "Declining"
#         else:
#             status = "Stable"

#         flags = []
#         if latest < 85:
#             flags.append("UNDER_OCCUPIED")

#         if dfm["physical_occupancy"].tail(3).is_monotonic_decreasing:
#             flags.append("CONTINUOUS_DECLINE_WARNING")

#         results.append(LeasingMomentumResponse(
#             property_id=pid,
#             property_name=pname,
#             momentum_status=status,
#             rolling_6m_occupancy=round(rolling_6m, 2),
#             early_warning_flags=flags,
#             performance_data=[MonthlyMetric(**m) for m in metrics]
#         ))

#     return results

class MonthlyPerformance(BaseModel):


    month: str

    property_id: int

    total_lettable_units: int

    leased_units: int

    vacant_units: int

    monthly_rental_revenue: float

    # Derived Parameters

    physical_occupancy_pct: float

    economic_occupancy_pct: float

    yoy_occupancy_change: float

    rolling_6m_occupancy_trend: float

    rolling_12m_revenue_trend: float

class LeasingMomentumResponse(BaseModel):

    property_name: str

    momentum_status: str

    assets_with_continuous_decline: bool

    early_warning_flags: List[str]

    data: List[MonthlyPerformance]

# --- Endpoint Logic ---

@app.get("/api/v1/analytics/leasing-momentum", response_model=List[LeasingMomentumResponse])

async def get_leasing_momentum(property_id: Optional[int] = Query(None)):

    """

    TASK L-01: Measure Leasing Performance Momentum.

    Features: Overlap Contract Logic, Time-Series Resampling, and Accurate YoY Analytics.

    """

    # 1. Fetch raw data: Properties, Units, and ALL Contracts within the last 36 months

    # We use 36 months to ensure we have data for a full 12-month YoY lookback for the 24-month display.

    sql_query = text("""

        SELECT

            p.ID as PropertyID,

            p.NAME as PropertyName,

            c.START_DATE,

            c.END_DATE,

            cu.UNIT_ID,

            cc.TOTAL_AMOUNT as ChargeAmount,

            (SELECT COUNT(*) FROM TERP_LS_PROPERTY_UNIT pu WHERE pu.PROPERTY_ID = p.ID) as TotalUnits

        FROM TERP_LS_PROPERTY p

        LEFT JOIN TERP_LS_CONTRACT c ON p.ID = c.PROPERTY_ID

        LEFT JOIN TERP_LS_CONTRACT_UNIT cu ON c.ID = cu.CONTRACT_ID

        LEFT JOIN TERP_LS_CONTRACT_CHARGES cc ON c.ID = cc.CONTRACT_ID

        WHERE (:p_id IS NULL OR p.ID = :p_id)

          AND (c.END_DATE >= DATE_SUB(CURRENT_DATE, INTERVAL 36 MONTH) OR c.ID IS NULL)

    """)

    try:

        with engine.connect() as conn:

            result = conn.execute(sql_query, {"p_id": property_id})

            df_raw = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df_raw.empty:

            return []

        # 2. Setup Time-Series (Last 36 months)

        report_months = pd.date_range(end=pd.Timestamp.now(), periods=36, freq='MS').strftime('%Y-%m-01')

        final_report = []

        for pid, p_group in df_raw.groupby('PropertyID'):

            p_name = p_group['PropertyName'].iloc[0]

            total_capacity = int(p_group['TotalUnits'].iloc[0])

            monthly_list = []

            for month in report_months:

                m_date = pd.to_datetime(month)

                # OVERLAP LOGIC: A unit is "Leased" if the contract started before/on month

                # AND ends after/on month.

                active_mask = (pd.to_datetime(p_group['START_DATE']) <= m_date) & \
                    (pd.to_datetime(p_group['END_DATE']) >= m_date)

                active_data = p_group[active_mask]

                leased_count = active_data['UNIT_ID'].nunique()

                revenue = active_data['ChargeAmount'].sum()

                monthly_list.append({

                    "month": month,

                    "property_id": pid,

                    "total_lettable_units": total_capacity,

                    "leased_units": leased_count,

                    "vacant_units": total_capacity - leased_count,

                    "monthly_rental_revenue": float(revenue),

                    "physical_occupancy_pct": round((leased_count / total_capacity * 100), 2) if total_capacity > 0 else 0

                })

            # 3. Convert to DataFrame for Advanced Analytics

            m_df = pd.DataFrame(monthly_list)

            # Derived Parameter: Economic Occupancy (Actual vs Max Possible)

            max_rev = m_df['monthly_rental_revenue'].max()

            m_df['economic_occupancy_pct'] = (m_df['monthly_rental_revenue'] / (max_rev if max_rev > 0 else 1)) * 100

            # Derived Parameter: YoY Occupancy Change (Exact 12-month difference)

            m_df['yoy_occupancy_change'] = m_df['physical_occupancy_pct'].diff(periods=12)

            # Derived Parameter: Rolling 6-Month Occupancy

            m_df['rolling_6m_occupancy_trend'] = m_df['physical_occupancy_pct'].rolling(window=6).mean()

            # Derived Parameter: Rolling 12-Month Revenue

            m_df['rolling_12m_revenue_trend'] = m_df['monthly_rental_revenue'].rolling(window=12).mean()

            # 4. Output Parameters (Momentum & Flags)

            latest = m_df.iloc[-1]

            # Momentum Status

            status = "Stable"

            if latest['physical_occupancy_pct'] > (latest['rolling_6m_occupancy_trend'] + 0.5):

                status = "Improving"

            elif latest['physical_occupancy_pct'] < (latest['rolling_6m_occupancy_trend'] - 0.5):

                status = "Declining"

            # Continuous Decline Check (Last 3 months)

            last_3 = m_df['physical_occupancy_pct'].tail(3).tolist()

            is_laggard = len(last_3) == 3 and (last_3[0] > last_3[1] > last_3[2])

            # Flags

            flags = []

            if latest['physical_occupancy_pct'] < 80: flags.append("LOW_PHYSICAL_OCCUPANCY")

            if latest['yoy_occupancy_change'] < 0: flags.append("NEGATIVE_YOY_GROWTH")

            if latest['economic_occupancy_pct'] < 70: flags.append("REVENUE_EFFICIENCY_ALERT")

            # Final Cleanup: Return only the most recent 24 months

            final_data = m_df.tail(24).to_dict(orient='records')

            final_report.append(LeasingMomentumResponse(

                property_name=p_name,

                momentum_status=status,

                assets_with_continuous_decline=is_laggard,

                early_warning_flags=flags,

                data=[MonthlyPerformance(**row) for row in final_data]

            ))

        return final_report

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))





# ---------------- 3️⃣ ASSETS WITH CONTINUOUS DECLINE ----------------
@app.get("/api/v1/assets/continuous-decline", response_model=List[DecliningAssetResponse])
def continuous_decline(min_months: int = 3):

    with engine.connect() as conn:
        df = pd.read_sql(BASE_QUERY, conn)

    months = pd.date_range(end=pd.Timestamp.today(), periods=12, freq="MS")
    declining_assets = []

    for pid, grp in df.groupby("PropertyID"):
        pname = grp["PropertyName"].iloc[0]
        total_units = int(grp["TotalUnits"].iloc[0])
        occ = []

        for m in months:
            active = grp[
                (pd.to_datetime(grp["START_DATE"]) <= m) &
                (pd.to_datetime(grp["END_DATE"]) >= m)
            ]
            leased = active["UNIT_ID"].nunique()
            occ.append(leased / total_units if total_units else 0)

        decline_streak = sum(
            occ[i] > occ[i + 1]
            for i in range(len(occ) - 1)
        )

        if decline_streak >= min_months:
            declining_assets.append(
                DecliningAssetResponse(
                    property_id=pid,
                    property_name=pname,
                    decline_months=decline_streak
                )
            )

    return declining_assets


 
from datetime import datetime
from typing import Dict

@app.get("/api/v1/analytics/portfolio-summary", response_model=Dict)
async def get_portfolio_summary():
    # Uses the base SQL query logic to aggregate all property data
    sql_query = text("""
        SELECT 
            p.ID as PropertyID, p.NAME as PropertyName,
            c.START_DATE, c.END_DATE, cu.UNIT_ID, cc.TOTAL_AMOUNT as ChargeAmount,
            (SELECT COUNT(*) FROM TERP_LS_PROPERTY_UNIT pu WHERE pu.PROPERTY_ID = p.ID) as TotalUnits
        FROM TERP_LS_PROPERTY p
        LEFT JOIN TERP_LS_CONTRACT c ON p.ID = c.PROPERTY_ID
        LEFT JOIN TERP_LS_CONTRACT_UNIT cu ON c.ID = cu.CONTRACT_ID
        LEFT JOIN TERP_LS_CONTRACT_CHARGES cc ON c.ID = cc.CONTRACT_ID
        WHERE (c.END_DATE >= DATE_SUB(CURRENT_DATE, INTERVAL 12 MONTH) OR c.ID IS NULL)
    """)
    
    with engine.connect() as conn:
        df = pd.DataFrame(conn.execute(sql_query).fetchall())

    # Aggregation logic to find current status per property
    summary = []
    for pid, group in df.groupby('PropertyID'):
        total_units = group['TotalUnits'].iloc[0]
        # Calculate current leased units (Today)
        current_leased = group[(pd.to_datetime(group['START_DATE']) <= datetime.now()) & 
                               (pd.to_datetime(group['END_DATE']) >= datetime.now())]['UNIT_ID'].nunique()
        
        summary.append({
            "property_name": group['PropertyName'].iloc[0],
            "occupancy_rate": round((current_leased / total_units * 100), 2) if total_units > 0 else 0,
            "status": "Healthy" if (current_leased / total_units) > 0.9 else "At Risk"
        })
    
    return {"portfolio_health": summary}

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text
import pandas as pd

# 1. Ensure your Response Model matches the SQL output
class UnitAuditResponse(BaseModel):
    UnitID: int
    LastLeaseEnd: Optional[datetime] = None
    DaysVacant: Optional[int] = None
    MarketRentEstimate: float

@app.get("/api/v1/analytics/unit-audit/{property_id}", response_model=List[UnitAuditResponse])
async def get_unit_audit(property_id: int):
    sql_query = text("""
        SELECT 
            pu.ID as UnitID, 
            MAX(c.END_DATE) as LastLeaseEnd,
            DATEDIFF(CURRENT_DATE, MAX(c.END_DATE)) as DaysVacant,
            COALESCE((
                SELECT AVG(cc.TOTAL_AMOUNT) 
                FROM TERP_LS_CONTRACT_CHARGES cc 
                JOIN TERP_LS_CONTRACT c2 ON cc.CONTRACT_ID = c2.ID 
                WHERE c2.PROPERTY_ID = :p_id
            ), 0) as MarketRentEstimate
        FROM TERP_LS_PROPERTY_UNIT pu
        LEFT JOIN TERP_LS_CONTRACT_UNIT cu ON pu.ID = cu.UNIT_ID
        LEFT JOIN TERP_LS_CONTRACT c ON cu.CONTRACT_ID = c.ID
        WHERE pu.PROPERTY_ID = :p_id
        GROUP BY pu.ID
        HAVING UnitID NOT IN (
            SELECT cu2.UNIT_ID FROM TERP_LS_CONTRACT_UNIT cu2
            JOIN TERP_LS_CONTRACT c2 ON cu2.CONTRACT_ID = c2.ID
            WHERE CURRENT_DATE BETWEEN c2.START_DATE AND c2.END_DATE
        )
    """)
    
    try:
        with engine.connect() as conn:
            # FIX: Use .mappings() to convert Row objects into dictionary-like objects
            result = conn.execute(sql_query, {"p_id": property_id}).mappings().all()
            
            # Now dict(row) or even just returning the row works perfectly
            return [dict(row) for row in result]
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")