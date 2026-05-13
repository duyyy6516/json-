# 👉 Thư viện cần thiết
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import plotly.express as px
import io

# ==============================================================================
# --- CẤU HÌNH TRANG ---
# ==============================================================================
st.set_page_config(page_title="JSON Data Pro", layout="wide", page_icon="🌱")
st.title("🌱 Công cụ Phân tích Dữ liệu Nông Nghiệp")

# 👉 Khoảng giá trị hợp lệ để lọc nhiễu
KHOANG_TOI_UU = {
    'TEMPKK': (-10.0, 100.0),       
    'HUMIKK': (0.0, 100.0),        
    'SOIL_ASKK': (0.0, 200000.0),   
    'AS': (0.0, 200000.0),          
    'NHIỆT ĐỘ': (-10.0, 100.0),    
    'ĐỘ ẨM': (0.0, 100.0),          
    'PH': (0.0, 14.0),              
    'TBPH': (0.0, 14.0),         
    'EC': (0.0, 10000.0),          
    'TBEC': (0.0, 10000.0),        
    'N': (0.0, 2000.0),             
    'P': (0.0, 2000.0),             
    'K': (0.0, 2000.0)                
}

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ LÕI
# ==============================================================================

@st.cache_data
def normalize_keys(data):
    if isinstance(data, list):
        return [normalize_keys(item) for item in data]
    elif isinstance(data, dict):
        return {str(k).strip().lower(): normalize_keys(v) for k, v in data.items()}
    return data

@st.cache_data
def flatten_json(y):
    out = {}
    def flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], name + a + '.')
        elif isinstance(x, list):
            for i, a in enumerate(x):
                flatten(a, name + str(i) + '.')
        else:
            out[name[:-1]] = x
    flatten(y)
    return out

@st.cache_data
def load_and_process_data(file_bytes):
    try:
        raw_data = json.loads(file_bytes)
    except json.JSONDecodeError:
        raise ValueError("File tải lên không đúng định dạng JSON hợp lệ.")
        
    if isinstance(raw_data, dict): 
        raw_data = [raw_data]
    
    clean_json = normalize_keys(raw_data)
    df = pd.DataFrame([flatten_json(row) for row in clean_json])
    
    df = df.dropna(axis=1, how='all').loc[:, ~df.columns.duplicated()]
    df = df.replace(r'^\s*$', np.nan, regex=True)
    
    time_col = next((col for col in df.columns if 'time' in col.lower() or 'thời gian' in col.lower()), None)
    if time_col:
        # Sửa lỗi định dạng ngày tháng phổ biến
        df['_parsed_time'] = pd.to_datetime(
            df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), 
            errors='coerce'
        )
    return df, time_col

# ==============================================================================
# 2. CÁC HÀM TIỆN ÍCH
# ==============================================================================

def render_date_filter(min_date, max_date, key_prefix):
    """Hàm tạo bộ lọc lịch và tính toán khoảng thời gian"""
    if not min_date: return None, None
    
    mode = st.radio(
        "⏳ Kiểu lọc thời gian:", 
        ["Tùy chọn", "Tuần (7 ngày)", "Tháng", "Quý"], 
        horizontal=True, 
        key=f"mode_{key_prefix}"
    ) 
    
    start_d, end_d = min_date, max_date

    if mode == "Tùy chọn":
        sel_date = st.date_input("📅 Chọn khoảng ngày:", value=(min_date, max_date), 
                                 min_value=min_date, max_value=max_date, key=f"date_{key_prefix}")
        if isinstance(sel_date, (list, tuple)) and len(sel_date) == 2:
            start_d, end_d = sel_date
        elif isinstance(sel_date, (list, tuple)) and len(sel_date) == 1:
            start_d = end_d = sel_date[0]
    else:
        start_d = st.date_input("📅 Chọn ngày bắt đầu:", value=min_date, 
                                min_value=min_date, max_value=max_date, key=f"start_{key_prefix}")
        if start_d:
            start_dt = pd.to_datetime(start_d)
            if mode == "Tuần (7 ngày)":
                end_d = (start_dt + pd.Timedelta(days=6)).date()
            elif mode == "Tháng":
                end_d = (start_dt + pd.DateOffset(months=1) - pd.Timedelta(days=1)).date()
            elif mode == "Quý":
                end_d = (start_dt + pd.DateOffset(months=3) - pd.Timedelta(days=1)).date()
            
            end_d = min(end_d, max_date)
            st.success(f"🎯 Sẽ lọc từ: **{start_d:%d/%m/%Y}** đến **{end_d:%d/%m/%Y}**")
            
    return start_d, end_d

def extract_sensor_data(df, selected_cols):
    records = []
    cols_to_extract = ['_parsed_time'] + selected_cols
    working_df = df[cols_to_extract].dropna(subset=['_parsed_time'])
    
    for row in working_df.itertuples(index=False):
        main_time = row[0]
        date_str = main_time.strftime('%Y-%m-%d')
        
        for i, col_name in enumerate(selected_cols, start=1):
            val = str(row[i]).strip()
            if not val or val.lower() == 'nan': continue
                
            col_upper = col_name.upper()
            
            def process_val(v_str):
                try:
                    v = float(v_str)
                    if col_upper in ['PH', 'TBPH'] and v > 14: return v / 100.0
                    if col_upper in ['NHIỆT ĐỘ'] and v > 100: return v / 10.0
                    return v
                except: return None
                
            matches = re.findall(r'(\d{2}-\d{2}-\d{2})/([-+]?\d*\.?\d+)', val)
            
            if matches:
                for t_str, v_str in matches:
                    v_processed = process_val(v_str)
                    if v_processed is not None:
                        full_t_str = f"{date_str} {t_str.replace('-', ':')}"
                        records.append({'TG': pd.to_datetime(full_t_str), 'Giá trị': v_processed, 'Chỉ số': col_upper})
            else:
                num_match = re.search(r'[-+]?\d*\.?\d+', val)
                if num_match:
                    v_processed = process_val(num_match.group())
                    if v_processed is not None:
                        records.append({'TG': main_time, 'Giá trị': v_processed, 'Chỉ số': col_upper})
                        
    return pd.DataFrame(records)

def generate_chart(df, title, is_multi=False):
    num_points = len(df)
    use_webgl = num_points > 1000
    show_markers = num_points <= 1000 
    
    if is_multi:
        fig = px.line(df, x='TG', y='Giá trị', color='Chỉ số', markers=show_markers, 
                      render_mode='webgl' if use_webgl else 'svg',
                      color_discrete_sequence=px.colors.qualitative.Set1)
    else:
        fig = px.line(df, x='TG', y='Giá trị', markers=show_markers, 
                      render_mode='webgl' if use_webgl else 'svg')
        
    fig.update_layout(
        title=f"<b>{title}</b>", xaxis_title="Thời gian", yaxis_title="Giá trị",
        hovermode="x unified", dragmode='pan',
        xaxis=dict(rangeslider=dict(visible=False), type="date")
    )
    return fig, num_points

# ==============================================================================
# 3. GIAO DIỆN CHÍNH
# ==============================================================================

uploaded_file = st.file_uploader("Tải lên file JSON", type=['json'])

if uploaded_file is not None:
    try:
        with st.spinner("Đang xử lý dữ liệu..."):
            file_bytes = uploaded_file.getvalue().decode("utf-8")
            df, time_col = load_and_process_data(file_bytes)

        # --- SIDEBAR ---
        st.sidebar.markdown("### 🔍 BỘ LỌC TÙY CHỈNH")
        filterable_cols = [col for col in df.columns if col not in ['_parsed_time']]
        selected_key = st.sidebar.selectbox("1. Chọn trường lọc:", options=["-- Không lọc --"] + filterable_cols)
        
        if selected_key != "-- Không lọc --":
            unique_values = df[selected_key].dropna().astype(str).unique()
            selected_value = st.sidebar.selectbox(f"2. Giá trị cho '{selected_key.upper()}':", options=["Tất cả"] + list(unique_values))
            if selected_value != "Tất cả":
                df = df[df[selected_key].astype(str) == selected_value].reset_index(drop=True)

        exclude = [time_col, 'stt', 'tên khu', 'trạng thái', '_parsed_time']
        numeric_options = [c for c in df.columns if c not in exclude and '_id' not in c]

        min_d, max_d = None, None
        if '_parsed_time' in df.columns:
            valid_ts = df['_parsed_time'].dropna()
            if not valid_ts.empty:
                min_d, max_d = valid_ts.min().date(), valid_ts.max().date()

        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["🗂️ Bảng dữ liệu", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau"])

        # TAB 1
        with tab1:
            st.subheader("🌾 Bảng dữ liệu chi tiết")
            display_df = df.drop(columns=['_parsed_time'], errors='ignore').fillna("")
            st.download_button("📥 Tải xuống CSV", data=display_df.to_csv(index=False).encode('utf-8'), 
                               file_name='data.csv', use_container_width=True)
            st.dataframe(display_df, use_container_width=True)

        # TAB 2
        with tab2:
            st.write("⚙️ Thiết lập biểu đồ đơn lẻ")
            col1, col2 = st.columns([1, 2])
            with col1:
                start_d_2, end_d_2 = render_date_filter(min_d, max_d, "tab2")
                filter_data_2 = st.checkbox("✅ Lọc sạch nhiễu", value=True, key="f2")
            with col2:
                st.write("Chọn chỉ số:")
                cols_ui = st.columns(4)
                selected_keys_2 = [k for i, k in enumerate(numeric_options) if cols_ui[i % 4].checkbox(k.upper(), key=f"t2_{k}")]

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="btn2"):
                mask = (df['_parsed_time'].dt.date >= start_d_2) & (df['_parsed_time'].dt.date <= end_d_2)
                chart_df = extract_sensor_data(df[mask], selected_keys_2)
                
                if not chart_df.empty:
                    days_diff = (end_d_2 - start_d_2).days
                    rule = "1D" if days_diff > 2 else None
                    if rule: st.info("💡 Đã tự động gộp dữ liệu theo ngày.")

                    for col in selected_keys_2:
                        sub_df = chart_df[chart_df['Chỉ số'] == col.upper()]
                        if filter_data_2 and col.upper() in KHOANG_TOI_UU:
                            low, high = KHOANG_TOI_UU[col.upper()]
                            sub_df = sub_df[(sub_df['Giá trị'] >= low) & (sub_df['Giá trị'] <= high)]
                        
                        if sub_df.empty: continue
                        plot_data = sub_df.set_index('TG').resample(rule)['Giá trị'].mean().dropna().reset_index() if rule else sub_df
                        fig, pts = generate_chart(plot_data, f"Chỉ số: {col.upper()}")
                        st.plotly_chart(fig, use_container_width=True)
                else: st.info("Không có dữ liệu.")

        # TAB 3
        with tab3:
            st.write("⚙️ Thiết lập biểu đồ lồng nhau")
            col1_m, col2_m = st.columns([1, 2])
            with col1_m:
                st.write("Chọn chỉ số:")
                check_ui = st.columns(3)
                selected_keys_3 = [k for i, k in enumerate(numeric_options) if check_ui[i % 3].checkbox(k.upper(), key=f"t3_{k}")]
            with col2_m:
                start_d_3, end_d_3 = render_date_filter(min_d, max_d, "tab3")
                filter_data_3 = st.checkbox("✅ Lọc sạch nhiễu", value=True, key="f3")

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="btn3"):
                mask = (df['_parsed_time'].dt.date >= start_d_3) & (df['_parsed_time'].dt.date <= end_d_3)
                multi_df = extract_sensor_data(df[mask], selected_keys_3)
                
                if not multi_df.empty:
                    days_diff = (end_d_3 - start_d_3).days
                    rule = "1D" if days_diff > 2 else None
                    
                    clean_list = []
                    for col in selected_keys_3:
                        sub = multi_df[multi_df['Chỉ số'] == col.upper()]
                        if filter_data_3 and col.upper() in KHOANG_TOI_UU:
                            low, high = KHOANG_TOI_UU[col.upper()]
                            sub = sub[(sub['Giá trị'] >= low) & (sub['Giá trị'] <= high)]
                        clean_list.append(sub)
                    
                    final_df = pd.concat(clean_list)
                    if rule:
                        plot_data = final_df.set_index('TG').groupby('Chỉ số')['Giá trị'].resample(rule).mean().dropna().reset_index()
                    else:
                        plot_data = final_df
                    
                    fig, pts = generate_chart(plot_data, "Đối chiếu trực tiếp", is_multi=True)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Không có dữ liệu.")

    except Exception as e:
        st.error(f"Lỗi: {e}")
