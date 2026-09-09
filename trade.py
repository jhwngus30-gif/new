import os
import glob
import platform
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns

# -----------------------------------------------------------------------------
# 0. 현재 스크립트 실행 디렉터리 경로 설정
# -----------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()

# -----------------------------------------------------------------------------
# 1. 한글 폰트 설정 (동일 경로의 '온글잎 콘콘체.ttf' 우선 적용)
# -----------------------------------------------------------------------------
def setup_korean_font():
    font_loaded = False
    
    # 1) 현재 폴더의 .ttf / .otf 폰트 검색 (온글잎 콘콘체.ttf 우선 탐색)
    font_candidates = [
        os.path.join(CURRENT_DIR, "온글잎 콘콘체.ttf"),
        *glob.glob(os.path.join(CURRENT_DIR, "*.ttf")),
        *glob.glob(os.path.join(CURRENT_DIR, "*.otf"))
    ]
    
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                fm.fontManager.addfont(fpath)
                font_prop = fm.FontProperties(fname=fpath)
                font_name = font_prop.get_name()
                plt.rc("font", family=font_name)
                font_loaded = True
                break
            except Exception:
                continue

    # 2) 폰트 파일 로드 실패 시 OS 기본 한글 폰트로 폴백
    if not font_loaded:
        sys_os = platform.system()
        if sys_os == "Windows":
            plt.rc("font", family="Malgun Gothic")
        elif sys_os == "Darwin":
            plt.rc("font", family="AppleGothic")
        else:
            plt.rc("font", family="NanumGothic")

    plt.rc("axes", unicode_minus=False)

setup_korean_font()

# Streamlit 페이지 설정
st.set_page_config(
    page_title="무역 분석 대시보드",
    page_icon="🌍",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. 같은 경로의 CSV 파일 로드 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 파일명 오탈자(sample / samples) 모두 유연하게 대응
    baci_path = os.path.join(CURRENT_DIR, "baci_85_sample.csv")
    
    country_candidates = [
        os.path.join(CURRENT_DIR, "country_codes_sample.csv"),
        os.path.join(CURRENT_DIR, "country_codes_samples.csv")
    ]
    country_path = next((p for p in country_candidates if os.path.exists(p)), None)

    if not os.path.exists(baci_path):
        raise FileNotFoundError(f"baci_85_sample.csv 파일을 찾을 수 없습니다. (경로: {baci_path})")
    if country_path is None:
        raise FileNotFoundError(f"country_codes_sample.csv 파일을 찾을 수 없습니다. (경로: {CURRENT_DIR})")

    baci_df = pd.read_csv(baci_path)
    country_df = pd.read_csv(country_path)

    # 무역 상대국(수입국 j) 코드 매핑
    code_col = [c for c in country_df.columns if c in ["j", "i", "code", "country_code"]][0]
    name_col = [c for c in country_df.columns if "name" in c.lower() or "country" in c.lower()][0]
    
    country_dict = dict(zip(country_df[code_col], country_df[name_col]))
    
    # 국가명 컬럼 생성 (BACI의 상대국 'j'를 매핑, 없을 경우 'i' 매핑 시도)
    match_col = "j" if "j" in baci_df.columns else "i"
    baci_df["country_name"] = baci_df[match_col].map(country_dict).fillna(baci_df[match_col].astype(str))

    # 무역액 USD 환산 (BACI의 v는 천 달러 단위이므로 * 1,000)
    baci_df["trade_value_usd"] = baci_df["v"] * 1000

    # 무역액 등급 분할 (대, 중, 소) - 3분위수 기준
    baci_df["trade_grade"] = pd.qcut(
        baci_df["trade_value_usd"], 
        q=3, 
        labels=["소", "중", "대"]
    )
    return baci_df, country_df

try:
    df_raw, country_df = load_data()
except Exception as e:
    st.error(f"데이터 로드 에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 필터
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 필터 설정")

# 1) 국가 선택 필터
all_countries = sorted(df_raw["country_name"].unique())
selected_countries = st.sidebar.multiselect(
    "국가 선택 (미선택 시 전체)",
    options=all_countries,
    default=[]
)

# 2) 무역액 등급 필터 (대, 중, 소)
grade_options = ["대", "중", "소"]
selected_grades = st.sidebar.multiselect(
    "무역액 등급 선택",
    options=grade_options,
    default=grade_options
)

# 필터 적용
df = df_raw.copy()
if selected_countries:
    df = df[df["country_name"].isin(selected_countries)]
if selected_grades:
    df = df[df["trade_grade"].isin(selected_grades)]

# -----------------------------------------------------------------------------
# 4. 메인 화면 구성
# -----------------------------------------------------------------------------
# 1. 타이틀
st.title("🌍 무역 분석 대시보드")
st.markdown("---")

# 2. baci_85_sample.csv 파일의 결측치
st.subheader("📋 1. 원본 데이터(baci_85_sample.csv) 결측치 현황")
null_summary = pd.DataFrame({
    "컬럼명": df_raw.columns,
    "결측치 수": df_raw.isnull().sum().values,
    "결측치 비율(%)": (df_raw.isnull().mean() * 100).round(2).values
})

with st.expander("결측치 세부 현황 펼쳐보기", expanded=False):
    st.dataframe(null_summary.T, use_container_width=True)

# 3. 주요 지표 (총 거래건수 | 총 수출액)
st.subheader("📊 2. 주요 거래 지표")
col_kpi1, col_kpi2 = st.columns(2)

total_count = len(df)
total_value = df["trade_value_usd"].sum()

with col_kpi1:
    st.metric(label="총 거래건수", value=f"{total_count:,} 건")
with col_kpi2:
    st.metric(label="총 수출액 (달러)", value=f"${total_value:,.0f}")

st.markdown("---")

# 4. 국가*연도 수출액 히트맵(상위 8개국) | 무역국 등급분포
st.subheader("📈 3. 수출 분석 및 무역액 등급 분포")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("##### [상위 8개국] 국가 × 연도 수출액 히트맵")
    # 총 수출액 기준 상위 8개국 선정
    top_8 = df.groupby("country_name")["trade_value_usd"].sum().nlargest(8).index
    df_top8 = df[df["country_name"].isin(top_8)]
    
    if not df_top8.empty:
        pivot_data = df_top8.pivot_table(
            index="country_name",
            columns="t",
            values="trade_value_usd",
            aggfunc="sum",
            fill_value=0
        )
        fig_heat, ax_heat = plt.subplots(figsize=(7, 5))
        sns.heatmap(
            pivot_data, 
            cmap="YlGnBu", 
            fmt=".0f", 
            cbar_kws={'label': '수출액 (USD)'}, 
            ax=ax_heat
        )
        ax_heat.set_xlabel("연도")
        ax_heat.set_ylabel("국가명")
        st.pyplot(fig_heat)
    else:
        st.info("표시할 데이터가 없습니다.")

with col_chart2:
    st.markdown("##### 무역액 등급 분포 (대 / 중 / 소)")
    grade_series = df["trade_grade"].value_counts().reindex(["대", "중", "소"])
    
    fig_bar, ax_bar = plt.subplots(figsize=(6, 5))
    sns.barplot(x=grade_series.index, y=grade_series.values, palette="Blues_r", ax=ax_bar)
    ax_bar.set_xlabel("무역액 등급")
    ax_bar.set_ylabel("거래 건수")
    
    for p in ax_bar.patches:
        h = p.get_height()
        ax_bar.annotate(
            f"{int(h):,}건",
            (p.get_x() + p.get_width() / 2., h),
            ha='center', va='bottom', fontsize=10, xytext=(0, 4),
            textcoords='offset points'
        )
    st.pyplot(fig_bar)

st.markdown("---")

# 5. 상위 5개국 * 무역액 등급 교차표 (원본건수 / 정규화 비율)
st.subheader("📑 4. 상위 5개국 × 무역액 등급 교차표")
top_5 = df.groupby("country_name")["trade_value_usd"].sum().nlargest(5).index
df_top5 = df[df["country_name"].isin(top_5)]

if not df_top5.empty:
    tab_raw, tab_norm = st.tabs(["원본 건수 (Count)", "정규화 비율 (Normalized)"])
    
    # 1) 원본 건수 표
    ct_raw = pd.crosstab(
        df_top5["country_name"],
        df_top5["trade_grade"],
        margins=True,
        margins_name="총합"
    ).reindex(columns=["대", "중", "소", "총합"])

    with tab_raw:
        st.markdown("###### ▪ 원본 거래 건수")
        st.dataframe(ct_raw, use_container_width=True)

    # 2) 국가별 정규화 비율 표 (%)
    ct_norm = pd.crosstab(
        df_top5["country_name"],
        df_top5["trade_grade"],
        normalize="index"
    ).reindex(columns=["대", "중", "소"]) * 100

    with tab_norm:
        st.markdown("###### ▪ 국가별 무역액 등급 비중 (%)")
        st.dataframe(ct_norm.round(2).astype(str) + " %", use_container_width=True)
else:
    st.info("해당 조건에 부합하는 데이터가 없습니다.")