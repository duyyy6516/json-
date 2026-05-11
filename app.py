import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import plotly.express as px
import io

# ==============================================================================
# --- CẤU HÌNH TRANG & THÔNG SỐ TỐI ƯU ---
# ==============================================================================
st.set_page_config(page_title="JSON Data Pro", layout="wide", page_icon="🌱")
st.title("🌱 Công cụ Phân tích Dữ liệu Nông Nghiệp")

# KHOẢNG TỐI ƯU ĐÃ ĐƯỢC ĐƯA VỀ CHUẨN THỰC TẾ (Vì dữ liệu đã được tự động quy đổi)
KHOANG_TOI_UU = {
    'TEMPKK': (-10.0, 100.0),       
    'HUMIKK': (0.0, 100.0),        
    'SOIL_ASKK': (0.0, 200000.0),   
    'AS': (0.0, 200000.0),          
    
    'NHIỆT ĐỘ': (-10.0, 100.0),    # Đã về chuẩn (vd: 33.1 độ)
    'ĐỘ ẨM': (0.0, 100.0),          
    
    'PH': (0.0, 14.0),             # Đã về chuẩn 0 - 14
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
        df['_parsed_time'] = pd.to_datetime(
            df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), 
            errors='coerce'
        )
    return df, time_col

# ==============================================================================
# 2. CÁC HÀM TIỆN ÍCH CHO BIỂU ĐỒ (ĐÃ NÂNG CẤP TỰ ĐỘNG QUY ĐỔI)
# ==============================================================================
def extract_sensor_data(df, selected_cols):
    records = []
    cols_to_extract = ['_parsed_time'] + selected_cols
    working_df = df[cols_to_extract].dropna(subset=['_parsed_time'])
    
    for row in working_df.itertuples(index=False):
        main_time = row[0]
        for i, col_name in enumerate(selected_cols, start=1):
            val = str(row[i]).strip()
            if not val or val.lower() == 'nan':
                continue
                
            col_upper = col_name.upper()
            
            # --- LOGIC TỰ ĐỘNG QUY ĐỔI SỐ LIỆU CẢM BIẾN ---
            def process_val(v_str):
                v = float(v_str)
                # Nếu pH > 14 (ví dụ 650.0), tự chia 100 để về 6.5
                if col_upper in ['PH', 'TBPH'] and v > 14:
                    return v / 100.0
                # Nếu Nhiệt độ > 100 (ví dụ 331.0), tự chia 10 để về 33.1
                if col_upper in ['NHIỆT ĐỘ'] and v > 100:
                    return v / 10.0
                return v
            # ----------------------------------------------
                
            matches = re.findall(r'(\d{2}-\d{2}-\d{2})/([-+]?\d*\.?\d+)', val)
            if matches:
                for t_str, v_str in matches:
                    try:
                        full_t_str = f"{main_time.strftime('%Y-%m-%d')} {t_str.replace('-', ':')}"
                        records.append({'TG': pd.to_datetime(full_t_str), 'Giá trị': process_val(v_str), 'Chỉ số': col_upper})
                    except Exception:
                        pass
            else:
                num_match = re.search(r'[-+]?\d*\.?\d+', val)
                if num_match:
                    records.append({'TG': main_time, 'Giá trị': process_val(num_match.group()), 'Chỉ số': col_upper})
                    
    return pd.DataFrame(records)

def generate_chart(df, title, is_multi=False):
    num_points = len(df)
    use_webgl = 'webgl' if num_points > 1000 else 'svg'
    show_markers = num_points <= 1000 
    
    if is_multi:
        # Ép sử dụng bảng màu Set1 (Tương phản mạnh: Đỏ, Xanh lam, Xanh lá, Tím, Cam, Vàng, Nâu...)
        fig = px.line(df, x='TG', y='Giá trị', color='Chỉ số', markers=show_markers, render_mode=use_webgl,
                      color_discrete_sequence=px.colors.qualitative.Set1)
    else:
        fig = px.line(df, x='TG', y='Giá trị', markers=show_markers, render_mode=use_webgl)
        
    fig.update_layout(
        title=f"<b>{title}</b>", xaxis_title="Thời gian", yaxis_title="Giá trị",
        hovermode="x unified", dragmode='pan',
        xaxis=dict(rangeslider=dict(visible=False), type="date")
    )
    fig.update_xaxes(showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
    fig.update_yaxes(showspikes=True, spikecolor="gray", spikemode="across")
    return fig, num_points

# ==============================================================================
# 3. XỬ LÝ GIAO DIỆN & FILE UPLOAD
# ==============================================================================
uploaded_file = st.file_uploader("Tải lên file JSON", type=['json'])

if uploaded_file is not None:
    try:
        with st.spinner("Đang xử lý dữ liệu..."):
            file_bytes = uploaded_file.getvalue().decode("utf-8")
            df, time_col = load_and_process_data(file_bytes)

        # ==============================================================================
        # TÍNH NĂNG LỌC LINH HOẠT THEO KEY BẤT KỲ (TÍCH HỢP Ở THANH BÊN)
        # ==============================================================================
        st.sidebar.markdown("### 🔍 BỘ LỌC TÙY CHỈNH")
        
        # Lấy danh sách tất cả các cột có thể lọc (bỏ qua cột thời gian nội bộ)
        filterable_cols = [col for col in df.columns if col not in ['_parsed_time']]
        
        # 1. Người dùng chọn Key (cột) muốn lọc
        selected_key = st.sidebar.selectbox(
            "1. Chọn trường dữ liệu (Key) muốn lọc:", 
            options=["-- Không lọc --"] + filterable_cols
        )
        
        # 2. Nếu đã chọn Key, hiển thị tiếp danh sách các giá trị của Key đó
        if selected_key != "-- Không lọc --":
            unique_values = df[selected_key].dropna().astype(str).unique()
            list_values = ["Tất cả"] + list(unique_values)
            
            selected_value = st.sidebar.selectbox(
                f"2. Chọn giá trị cho '{selected_key.upper()}':", 
                options=list_values
            )
            
            # 3. Tiến hành cắt DataFrame
            if selected_value != "Tất cả":
                df = df[df[selected_key].astype(str) == selected_value].reset_index(drop=True)
                st.sidebar.success(f"✅ Đang lọc: {selected_key.upper()} = {selected_value}")
                
                if df.empty:
                    st.error("⚠️ Bộ lọc này không trả về kết quả nào. Vui lòng chọn giá trị khác!")
                    st.stop()
        # ==============================================================================

        # Đã bỏ 'mùa vụ' khỏi danh sách exclude
        exclude = [time_col, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển', '_parsed_time']
        numeric_options = [c for c in df.columns if c not in exclude and '_id' not in c]

        min_d, max_d = None, None
        if '_parsed_time' in df.columns:
            valid_ts = df['_parsed_time'].dropna()
            if not valid_ts.empty:
                min_d, max_d = valid_ts.min().date(), valid_ts.max().date()

        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["🗂️ Bảng dữ liệu", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau"])

        # ==========================================
        # TAB 1: BẢNG DỮ LIỆU
        # ==========================================
        with tab1:
            st.subheader("🌾 Bảng dữ liệu chi tiết")
            
            # Ẩn các cột hỗ trợ tính toán nội bộ khi hiển thị cho người dùng
            display_df = df.drop(columns=['_parsed_time'], errors='ignore').fillna("")

            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.write(f"Đang hiển thị: **{len(df)}** bản ghi (dựa theo bộ lọc hiện tại)")
            with col_h2:
                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Tải xuống CSV", data=csv, file_name='data_export.csv', mime='text/csv', use_container_width=True)
                
            st.dataframe(display_df, use_container_width=True)

        # ==========================================
        # TAB 2: BIỂU ĐỒ ĐƠN LẺ
        # ==========================================
        with tab2:
            st.write("⚙️ Thiết lập biểu đồ đơn lẻ")
            col1, col2 = st.columns([1, 2])
            with col1:
                sel_date_2 = st.date_input("Lọc theo ngày:", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="date_tab2") if min_d else None
                start_d_2 = sel_date_2[0] if sel_date_2 else None
                end_d_2 = sel_date_2[1] if sel_date_2 and len(sel_date_2) == 2 else start_d_2
                res_choice_2 = st.selectbox("Làm mượt:", ["Nguyên bản", "TB mỗi phút", "TB mỗi 5 phút"], key="res_tab2")
                r_dict = {"Nguyên bản": None, "TB mỗi phút": "1min", "TB mỗi 5 phút": "5min"}
                
                filter_data_2 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, help="Tích vào để lọc bỏ các thông số ảo. Bỏ tích để xem số liệu nguyên gốc.")

            with col2:
                st.write("Chọn chỉ số:")
                cols_ui = st.columns(4)
                selected_keys_2 = [k for i, k in enumerate(numeric_options) if cols_ui[i % 4].checkbox(k.upper(), key=f"c_tab2_{k}")]

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="btn_tab2"):
                if not selected_keys_2:
                    st.warning("Hãy chọn ít nhất 1 chỉ số!")
                else:
                    mask = (df['_parsed_time'].dt.date >= start_d_2) & (df['_parsed_time'].dt.date <= end_d_2)
                    filtered_df = df[mask]
                    chart_df = extract_sensor_data(filtered_df, selected_keys_2) 
                    
                    if not chart_df.empty:
                        rule = r_dict[res_choice_2]
                        if start_d_2 and end_d_2 and (end_d_2 - start_d_2).days > 7 and not rule: rule = "5min"
                        for col in selected_keys_2:
                            sub_df = chart_df[chart_df['Chỉ số'] == col.upper()]
                            ten_chi_so = col.upper()
                            
                            if filter_data_2 and ten_chi_so in KHOANG_TOI_UU:
                                min_val, max_val = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_val) & (sub_df['Giá trị'] <= max_val)]
                            
                            if sub_df.empty: continue
                            
                            if rule: plot_data = sub_df.set_index('TG').resample(rule)['Giá trị'].mean().dropna().reset_index()
                            else: plot_data = sub_df.groupby('TG')['Giá trị'].mean().reset_index()
                            plot_data = plot_data.sort_values(by='TG')
                            
                            fig, pts = generate_chart(plot_data, f"Chỉ số: {ten_chi_so}", is_multi=False)
                            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                            
                            trang_thai_loc = "Đã lọc sạch" if filter_data_2 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu của biểu đồ trên để đối chứng ({pts} điểm - {trang_thai_loc})"):
                                st.dataframe(plot_data, use_container_width=True)
                            st.write("---")
                    else: st.info("Không có dữ liệu hợp lệ.")

        # ==========================================
        # TAB 3: BIỂU ĐỒ LỒNG NHAU 
        # ==========================================
        with tab3:
            st.write("⚙️ Thiết lập biểu đồ lồng nhau")
            col1_m, col2_m = st.columns([1, 2])
            with col1_m:
                st.write("🎯 **Chọn chỉ số:**")
                check_multi_ui = st.columns(3)
                selected_keys_3 = [k for i, k in enumerate(numeric_options) if check_multi_ui[i % 3].checkbox(k.upper(), key=f"c_multi_{k}")]

            with col2_m:
                sel_date_3 = st.date_input("Lọc theo ngày:", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="date_multi") if min_d else None
                start_d_3 = sel_date_3[0] if sel_date_3 else None
                end_d_3 = sel_date_3[1] if sel_date_3 and len(sel_date_3) == 2 else start_d_3
                res_choice_3 = st.selectbox("Làm mượt:", ["Nguyên bản", "TB mỗi phút", "TB mỗi 5 phút"], key="res_multi")
                
                filter_data_3 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, help="Tích vào để lọc bỏ các thông số ảo. Bỏ tích để xem số liệu nguyên gốc.", key="filter_tab3")

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="btn_multi"):
                if len(selected_keys_3) < 2:
                    st.warning("Hãy chọn ít nhất 2 chỉ số!")
                else:
                    mask = (df['_parsed_time'].dt.date >= start_d_3) & (df['_parsed_time'].dt.date <= end_d_3)
                    filtered_df = df[mask]
                    multi_chart_df = extract_sensor_data(filtered_df, selected_keys_3) 
                    
                    if not multi_chart_df.empty:
                        clean_dfs = []
                        for col in selected_keys_3:
                            sub_df = multi_chart_df[multi_chart_df['Chỉ số'] == col.upper()]
                            ten_chi_so = col.upper()
                            
                            if filter_data_3 and ten_chi_so in KHOANG_TOI_UU:
                                min_val, max_val = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_val) & (sub_df['Giá trị'] <= max_val)]
                                
                            if not sub_df.empty: clean_dfs.append(sub_df)
                            
                        multi_chart_df = pd.concat(clean_dfs) if clean_dfs else pd.DataFrame()
                        
                        if not multi_chart_df.empty:
                            rule = r_dict[res_choice_3]
                            if start_d_3 and end_d_3 and (end_d_3 - start_d_3).days > 7 and not rule: rule = "5min"
                            if rule: plot_data = multi_chart_df.set_index('TG').groupby('Chỉ số')['Giá trị'].resample(rule).mean().dropna().reset_index()
                            else: plot_data = multi_chart_df.groupby(['TG', 'Chỉ số'])['Giá trị'].mean().reset_index()
                            plot_data = plot_data.sort_values(by='TG')
                            
                            fig, pts = generate_chart(plot_data, f"Biểu đồ Đối chiếu Trực tiếp", is_multi=True)
                            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                            
                            trang_thai_loc_3 = "Đã lọc sạch" if filter_data_3 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu gộp của biểu đồ trên để đối chứng ({pts} điểm - {trang_thai_loc_3})"):
                                pivot_df = plot_data.pivot(index='TG', columns='Chỉ số', values='Giá trị').reset_index()
                                st.dataframe(pivot_df, use_container_width=True)
                    else: st.info("Không có dữ liệu hợp lệ.")

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
