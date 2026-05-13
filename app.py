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
        df['_parsed_time'] = pd.to_datetime(
            df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), 
            errors='coerce'
        )
    return df, time_col

# ==============================================================================
# 2. CÁC HÀM TIỆN ÍCH CHO BIỂU ĐỒ & BỘ LỌC
# ==============================================================================
def render_date_filter(min_date, max_date, key_prefix):
    if not min_date: return None, None
    
    mode = st.radio(
        "⏳ Kiểu lọc thời gian:", 
        ["Tùy chọn", "Theo Tuần (7 ngày)", "Theo Tháng", "Theo Quý"], 
        horizontal=True, 
        key=f"mode_{key_prefix}"
    )
    
    if mode == "Tùy chọn":
        sel_date = st.date_input("📅 Chọn khoảng ngày:", value=(min_date, max_date), min_value=min_date, max_value=max_date, key=f"date_{key_prefix}")
        if isinstance(sel_date, tuple) and len(sel_date) == 2:
            start_d, end_d = sel_date
        else:
            start_d = sel_date[0] if isinstance(sel_date, list) or isinstance(sel_date, tuple) else sel_date
            end_d = start_d
    else:
        start_d = st.date_input("📅 Chọn ngày bắt đầu:", value=min_date, min_value=min_date, max_value=max_date, key=f"start_{key_prefix}")
        if start_d:
            if mode == "Theo Tuần (7 ngày)":
                end_d = (pd.to_datetime(start_d) + pd.Timedelta(days=6)).date()
            elif mode == "Theo Tháng":
                end_d = (pd.to_datetime(start_d) + pd.DateOffset(months=1) - pd.Timedelta(days=1)).date()
            elif mode == "Theo Quý":
                end_d = (pd.to_datetime(start_d) + pd.DateOffset(months=3) - pd.Timedelta(days=1)).date()
            
            if end_d > max_date:
                end_d = max_date
            st.success(f"🎯 Sẽ lọc từ: **{start_d.strftime('%d/%m/%Y')}** đến **{end_d.strftime('%d/%m/%Y')}**")
        else:
            end_d = None
            
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
            if not val or val.lower() == 'nan':
                continue
                
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
                    try:
                        full_t_str = f"{date_str} {t_str.replace('-', ':')}"
                        proc_v = process_val(v_str)
                        if proc_v is not None:
                            records.append({'TG': pd.to_datetime(full_t_str), 'Giá trị': proc_v, 'Chỉ số': col_upper})
                    except: pass
            else:
                num_match = re.search(r'[-+]?\d*\.?\d+', val)
                if num_match:
                    proc_v = process_val(num_match.group())
                    if proc_v is not None:
                        records.append({'TG': main_time, 'Giá trị': proc_v, 'Chỉ số': col_upper})
                    
    return pd.DataFrame(records)

def generate_chart(df, title, is_multi=False):
    num_points = len(df)
    use_webgl = 'webgl' if num_points > 1000 else 'svg'
    show_markers = num_points <= 1000 
    
    if is_multi:
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

        st.sidebar.markdown("### 🔍 BỘ LỌC TÙY CHỈNH")
        filterable_cols = [col for col in df.columns if col not in ['_parsed_time']]
        selected_key = st.sidebar.selectbox("1. Chọn trường dữ liệu (Key) muốn lọc:", options=["-- Không lọc --"] + filterable_cols)
        
        if selected_key != "-- Không lọc --":
            unique_values = df[selected_key].dropna().astype(str).unique()
            list_values = ["Tất cả"] + list(unique_values)
            selected_value = st.sidebar.selectbox(f"2. Chọn giá trị cho '{selected_key.upper()}':", options=list_values)
            
            if selected_value != "Tất cả":
                df = df[df[selected_key].astype(str) == selected_value].reset_index(drop=True)
                st.sidebar.success(f"✅ Đang lọc: {selected_key.upper()} = {selected_value}")
                if df.empty:
                    st.error("⚠️ Bộ lọc này không trả về kết quả nào.")
                    st.stop()

        exclude = [time_col, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển', '_parsed_time']
        numeric_options = [c for c in df.columns if c not in exclude and '_id' not in c]

        min_d, max_d = None, None
        if '_parsed_time' in df.columns:
            valid_ts = df['_parsed_time'].dropna()
            if not valid_ts.empty:
                min_d, max_d = valid_ts.min().date(), valid_ts.max().date()

        tab1, tab2, tab3 = st.tabs(["🗂️ Bảng dữ liệu", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau"])

        # TAB 1: BẢNG DỮ LIỆU
        with tab1:
            st.subheader("🌾 Bảng dữ liệu chi tiết")
            display_df = df.drop(columns=['_parsed_time'], errors='ignore').fillna("")
            st.write(f"Đang hiển thị: **{len(df)}** bản ghi")
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Tải xuống CSV", data=csv, file_name='data_export.csv', mime='text/csv')
            st.dataframe(display_df, use_container_width=True)

        # TAB 2: BIỂU ĐỒ ĐƠN LẺ
        with tab2:
            st.write("⚙️ Thiết lập biểu đồ đơn lẻ")
            col1, col2 = st.columns([1, 2])
            with col1:
                start_d_2, end_d_2 = render_date_filter(min_d, max_d, "tab2")
                filter_data_2 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch", value=True, key="filter_tab2")
            with col2:
                st.write("Chọn chỉ số:")
                cols_ui = st.columns(4)
                selected_keys_2 = [k for i, k in enumerate(numeric_options) if cols_ui[i % 4].checkbox(k.upper(), key=f"c_tab2_{k}")]

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="btn_tab2"):
                if not selected_keys_2 or not start_d_2 or not end_d_2:
                    st.warning("Vui lòng chọn đầy đủ thông số!")
                else:
                    mask = (df['_parsed_time'].dt.date >= start_d_2) & (df['_parsed_time'].dt.date <= end_d_2)
                    chart_df = extract_sensor_data(df[mask], selected_keys_2)
                    
                    if not chart_df.empty:
                        days_diff = (end_d_2 - start_d_2).days
                        if days_diff > 2:
                            st.info("💡 Khoảng thời gian > 2 ngày: Dữ liệu tất cả chỉ số đã được tính trung bình theo ngày.")

                        for col in selected_keys_2:
                            ten_chi_so = col.upper()
                            sub_df = chart_df[chart_df['Chỉ số'] == ten_chi_so]
                            
                            if filter_data_2 and ten_chi_so in KHOANG_TOI_UU:
                                min_v, max_v = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_v) & (sub_df['Giá trị'] <= max_v)]
                            
                            if sub_df.empty: continue
                            
                            # ÉP TRUNG BÌNH NẾU > 2 NGÀY CHO TẤT CẢ CÁC CHỈ SỐ
                            if days_diff > 2:
                                plot_data = sub_df.set_index('TG').resample('1D')['Giá trị'].mean().dropna().reset_index()
                            else:
                                plot_data = sub_df.groupby('TG')['Giá trị'].mean().reset_index()
                                
                            fig, pts = generate_chart(plot_data.sort_values('TG'), f"Chỉ số: {ten_chi_so}")
                            st.plotly_chart(fig, use_container_width=True)
                    else: st.info("Không có dữ liệu.")

        # TAB 3: BIỂU ĐỒ LỒNG NHAU
        with tab3:
            st.write("⚙️ Thiết lập biểu đồ lồng nhau")
            col1_m, col2_m = st.columns([1, 2])
            with col1_m:
                st.write("🎯 **Chọn chỉ số:**")
                check_multi_ui = st.columns(3)
                selected_keys_3 = [k for i, k in enumerate(numeric_options) if check_multi_ui[i % 3].checkbox(k.upper(), key=f"c_multi_{k}")]
            with col2_m:
                start_d_3, end_d_3 = render_date_filter(min_d, max_d, "tab3")
                filter_data_3 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch", value=True, key="filter_tab3")

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="btn_multi"):
                if len(selected_keys_3) < 2 or not start_d_3 or not end_d_3:
                    st.warning("Vui lòng chọn ít nhất 2 chỉ số và thời gian!")
                else:
                    mask = (df['_parsed_time'].dt.date >= start_d_3) & (df['_parsed_time'].dt.date <= end_d_3)
                    multi_chart_df = extract_sensor_data(df[mask], selected_keys_3)
                    
                    if not multi_chart_df.empty:
                        days_diff = (end_d_3 - start_d_3).days
                        if days_diff > 2:
                            st.info("💡 Khoảng thời gian > 2 ngày: Dữ liệu tất cả chỉ số đã được tính trung bình theo ngày.")

                        clean_dfs = []
                        for col in selected_keys_3:
                            ten_chi_so = col.upper()
                            sub_df = multi_chart_df[multi_chart_df['Chỉ số'] == ten_chi_so]
                            
                            if filter_data_3 and ten_chi_so in KHOANG_TOI_UU:
                                min_v, max_v = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_v) & (sub_df['Giá trị'] <= max_v)]
                                
                            if not sub_df.empty:
                                # ÉP TRUNG BÌNH CHO TẤT CẢ
                                if days_diff > 2:
                                    plot_sub = sub_df.set_index('TG').resample('1D')['Giá trị'].mean().dropna().reset_index()
                                else:
                                    plot_sub = sub_df.groupby('TG')['Giá trị'].mean().reset_index()
                                plot_sub['Chỉ số'] = ten_chi_so
                                clean_dfs.append(plot_sub)
                        
                        if clean_dfs:
                            final_df = pd.concat(clean_dfs).sort_values('TG')
                            fig, pts = generate_chart(final_df, "Biểu đồ Đối chiếu", is_multi=True)
                            st.plotly_chart(fig, use_container_width=True)
                    else: st.info("Không có dữ liệu.")

    except Exception as e:
        st.error(f"Lỗi: {e}")
"""
==============================================================================
DANH SÁCH CHI TIẾT CÁC CÔNG CỤ XỬ LÝ DỮ LIỆU TẬN GỐC (REGEX & DATA TOOLS)
==============================================================================

1. NHÓM CÔNG CỤ TRÍCH XUẤT (BÓC TÁCH)
------------------------------------------------------------------------------
* re.findall():
    - Xử lý: Quét toàn bộ chuỗi từ đầu đến cuối để nhặt RA TẤT CẢ các cặp thỏa mãn.
    - Trong code: Nhặt mọi cặp (Giờ-Phút-Giây)/(Giá trị) trong một chuỗi nén dài. 
    - Ví dụ: "08-00/25; 09-00/26" -> Trả về danh sách [('08-00', '25'), ('09-00', '26')].

* re.search():
    - Xử lý: Dừng lại ngay khi tìm thấy kết quả ĐẦU TIÊN thỏa mãn.
    - Trong code: Dùng để kiểm tra nhanh xem một ô dữ liệu có chứa số hay không trước khi xử lý. 
    - Ví dụ: "N: 25.5 mg" -> Nó chỉ nhặt đúng số '25.5' rồi nghỉ, không quan tâm chữ 'mg' phía sau.

* re.sub() (Tiềm năng):
    - Xử lý: Tìm và Thay thế.
    - Ứng dụng: Dùng để dọn dẹp các ký tự lạ như dấu chấm phẩy (;), dấu gạch đứng (|) thành dấu phẩy chuẩn trước khi tách mảng.

2. NHÓM CÔNG CỤ BIẾN ĐỔI (TRANSFORM)
------------------------------------------------------------------------------
* .replace(r'^\s*$', np.nan, regex=True):
    - Xử lý: Tìm các ô chỉ có dấu cách (trống rỗng) và biến chúng thành 'NaN' (Giá trị rỗng kỹ thuật).
    - Mục tiêu: Để khi tính trung bình (Mean), máy sẽ bỏ qua các ô này, không làm sai lệch kết quả.

* .astype(str).str.replace('-', ':'):
    - Xử lý: Sửa lỗi gõ sai ký tự thời gian.
    - Cụ thể: Biến "08-30-00" (dạng sai) thành "08:30:00" (dạng chuẩn) để Python hiểu được đó là Giờ:Phút.

* .pivot():
    - Xử lý: Xoay bảng dữ liệu.
    - Cụ thể: Biến dữ liệu dạng dọc (Chỉ số nằm trên 1 cột) thành dạng ngang (Mỗi chỉ số N, P, K là 1 cột riêng) để ông dễ xem trong Excel.

3. NHÓM CÔNG CỤ TÍNH TOÁN & GOM NHÓM (AGGREGATION)
------------------------------------------------------------------------------
* .resample('1D'):
    - Xử lý: "Cắt lát" thời gian theo đơn vị 1 ngày.
    - Cụ thể: Gom hàng trăm điểm dữ liệu lẻ tẻ của 24 tiếng đồng hồ vào một cái "giỏ" duy nhất đại diện cho ngày đó.

* .mean():
    - Xử lý: Tính trung bình cộng.
    - Cụ thể: Lấy tổng giá trị trong "giỏ" ngày đó chia cho số lượng điểm để ra con số ổn định nhất, loại bỏ các biến động nhiễu tức thời.

* .dropna():
    - Xử lý: Vứt bỏ các hàng dữ liệu bị thiếu/lỗi sau khi tính toán.
    - Mục tiêu: Đảm bảo biểu đồ là một đường liền mạch, không có các khoảng trắng vô nghĩa.

4. LOGIC TỰ ĐỘNG CHỈNH SAI SỐ (SMART CORRECTION)
------------------------------------------------------------------------------
* Logic PH > 14: Tự động chia 100 (Ví dụ: 750 -> 7.5).
* Logic Nhiệt độ > 100: Tự động chia 10 (Ví dụ: 255 -> 25.5).
* Logic EC > 10000: Loại bỏ vì coi là ngắn mạch hoặc cảm biến lỗi cực nặng.
==============================================================================
"""
