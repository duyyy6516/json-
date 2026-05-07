import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import plotly.express as px

# Cấu hình trang
st.set_page_config(page_title="JSON Data Pro", layout="wide")
st.title("📊 Công cụ Phân tích Dữ liệu")

# --- 1. TỐI ƯU HÓA HIỆU NĂNG VỚI CACHE & PANDAS VECTORIZATION ---
@st.cache_data
def normalize_keys(data):
    if isinstance(data, list):
        return [normalize_keys(item) for item in data]
    elif isinstance(data, dict):
        return {str(k).strip().lower(): normalize_keys(v) for k, v in data.items()}
    return data

@st.cache_data
def load_and_process_data(file_bytes):
    raw_data = json.loads(file_bytes)
    if isinstance(raw_data, dict): 
        raw_data = [raw_data]
    
    clean_json = normalize_keys(raw_data)
    
    # Tối ưu 1: Dùng hàm được viết bằng C của Pandas thay vì đệ quy thuần
    df = pd.json_normalize(clean_json, sep='.')
    
    df = df.dropna(axis=1, how='all').loc[:, ~df.columns.duplicated()]
    df = df.replace(r'^\s*$', np.nan, regex=True)
    return df

# Tối ưu 2: Hàm bóc tách dữ liệu áp dụng cho cả cột (Vectorized)
def extract_points(row_val, main_time, col_name=None):
    val = str(row_val).strip()
    if not val or val.lower() == 'nan':
        return []
    
    # Cập nhật Regex: Bắt cả dấu / và dấu ;
    matches = re.findall(r'(\d{2}-\d{2}-\d{2})[;/]([-+]?\d*\.?\d+)', val)
    
    points = []
    if matches:
        for t_str, v_str in matches:
            try:
                full_t_str = f"{pd.to_datetime(main_time).strftime('%Y-%m-%d')} {t_str.replace('-', ':')}"
                pt = {'TG': pd.to_datetime(full_t_str), 'Giá trị': float(v_str)}
                if col_name: 
                    pt['Loại chỉ số'] = col_name.upper()
                points.append(pt)
            except Exception:
                pass
    else:
        num_match = re.search(r'[-+]?\d*\.?\d+', val)
        if num_match:
            pt = {'TG': pd.to_datetime(main_time), 'Giá trị': float(num_match.group())}
            if col_name: 
                pt['Loại chỉ số'] = col_name.upper()
            points.append(pt)
            
    return points

# --- XỬ LÝ FILE UPLOAD ---
uploaded_file = st.file_uploader("Tải lên file JSON", type=['json'])

if uploaded_file is not None:
    try:
        # Xử lý dữ liệu ban đầu
        file_bytes = uploaded_file.getvalue().decode("utf-8")
        df = load_and_process_data(file_bytes)
        display_df = df.fillna("")

        # --- TẠO 3 TABS ĐỘC LẬP ---
        tab1, tab2, tab3 = st.tabs(["🗂️ Bảng dữ liệu gốc", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau (So sánh)"])

        # -------------------------------------------------------------
        # TAB 1: HIỂN THỊ DỮ LIỆU
        # -------------------------------------------------------------
        with tab1:
            st.subheader(f"🗂️ Bảng dữ liệu gốc ({len(df)} bản ghi)")
            st.data_editor(display_df, use_container_width=True, key="editor_tab1")

        # -------------------------------------------------------------
        # TAB 2: VẼ BIỂU ĐỒ ĐƠN LẺ
        # -------------------------------------------------------------
        with tab2:
            st.subheader("⚙️ Thiết lập biểu đồ đơn lẻ")
            
            time_col = next((col for col in df.columns if 'time' in col.lower() or 'thời gian' in col.lower()), None)
            start_d, end_d = None, None
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if time_col:
                    t_dates = pd.to_datetime(df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), errors='coerce')
                    valid_ts = t_dates.dropna()
                    if not valid_ts.empty:
                        min_d, max_d = valid_ts.min().date(), valid_ts.max().date()
                        sel_date = st.date_input("Lọc theo ngày:", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="date_tab2")
                        start_d, end_d = (sel_date[0], sel_date[1]) if len(sel_date) == 2 else (sel_date[0], sel_date[0])
                
                resample_choice = st.selectbox(
                    "Làm mượt dữ liệu:", 
                    ["Nguyên bản", "Trung bình mỗi phút", "Trung bình mỗi 5 phút"], 
                    key="res_tab2"
                )
                resample_dict = {"Nguyên bản": None, "Trung bình mỗi phút": "1min", "Trung bình mỗi 5 phút": "5min"}

            with col2:
                exclude = [time_col, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển']
                numeric_options = [c for c in df.columns if c not in exclude and '_id' not in c]
                
                st.write("Chọn chỉ số vẽ biểu đồ:")
                cols_ui = st.columns(4)
                selected_keys = [k for i, k in enumerate(numeric_options) if cols_ui[i % 4].checkbox(k.upper(), key=f"c_tab2_{k}")]

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="btn_tab2"):
                if not selected_keys:
                    st.warning("Hãy chọn ít nhất 1 chỉ số!")
                else:
                    working_df = df.copy()
                    if time_col and start_d and end_d:
                        working_df[time_col] = pd.to_datetime(working_df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), errors='coerce')
                        working_df = working_df.dropna(subset=[time_col])
                        mask = (working_df[time_col].dt.date >= start_d) & (working_df[time_col].dt.date <= end_d)
                        working_df = working_df[mask]

                    for col in selected_keys:
                        # Tối ưu 3: Thay thế iterrows bằng apply để xử lý song song siêu tốc
                        extracted_series = working_df.apply(lambda row: extract_points(row[col], row[time_col]), axis=1)
                        all_points = []
                        for pts in extracted_series:
                            if isinstance(pts, list):
                                all_points.extend(pts)
                        
                        if all_points:
                            chart_df = pd.DataFrame(all_points)
                            rule = resample_dict[resample_choice]
                            
                            # Tính năng ép làm mượt
                            if start_d and end_d:
                                delta_days = (end_d - start_d).days
                                if delta_days > 7 and not rule:
                                    st.warning(f"⚠️ Khoảng thời gian chọn quá dài ({delta_days} ngày). Hệ thống tự động chuyển '{col.upper()}' sang 'Trung bình mỗi 5 phút' để tránh treo trình duyệt.")
                                    rule = "5min"

                            if rule:
                                plot_data = chart_df.set_index('TG').resample(rule)['Giá trị'].mean().dropna().reset_index()
                            else:
                                plot_data = chart_df.groupby('TG')['Giá trị'].mean().reset_index()

                            if not plot_data.empty:
                                plot_data = plot_data.sort_values(by='TG')
                                st.write(f"### Biểu đồ: {col.upper()}")
                                
                                num_points = len(plot_data)
                                use_webgl = 'webgl' if num_points > 1000 else 'svg'
                                show_markers = num_points <= 1000 

                                fig = px.line(plot_data, x='TG', y='Giá trị', markers=show_markers, render_mode=use_webgl)
                                fig.update_layout(
                                    xaxis_title="Thời gian (TG)",
                                    yaxis_title=f"Giá trị ({col.upper()})",
                                    hovermode="x unified",
                                    dragmode='pan',
                                    xaxis=dict(rangeslider=dict(visible=False), type="date")
                                )
                                
                                fig.update_xaxes(showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
                                fig.update_yaxes(showspikes=True, spikecolor="gray", spikemode="across")
                                
                                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                                
                                with st.expander(f"Xem chi tiết {num_points} điểm dữ liệu cho {col.upper()}"):
                                    st.dataframe(plot_data, use_container_width=True)
                                st.write("---")

        # -------------------------------------------------------------
        # TAB 3: VẼ BIỂU ĐỒ LỒNG NHAU (SO SÁNH MULTI-LINE)
        # -------------------------------------------------------------
        with tab3:
            st.subheader("⚙️ Thiết lập biểu đồ đối chiếu lồng nhau (Giá trị thực tế)")
            st.info("Chức năng này so sánh các thông số dựa trên giá trị thực của chúng.")

            time_col_multi = next((col for col in df.columns if 'time' in col.lower() or 'thời gian' in col.lower()), None)
            exclude_m = [time_col_multi, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển']
            numeric_opts_multi = [c for c in df.columns if c not in exclude_m and '_id' not in c]

            col1_m, col2_m = st.columns([1, 2])
            
            with col1_m:
                st.write("🎯 **1. Chọn các chỉ số:**")
                check_multi_ui = st.columns(3)
                selected_comparison_keys = [k for i, k in enumerate(numeric_opts_multi) if check_multi_ui[i % 3].checkbox(k.upper(), key=f"c_multi_{k}")]

            with col2_m:
                st.write("✨ **2. Tùy chỉnh:**")
                start_d_m, end_d_m = None, None
                if time_col_multi:
                    t_dates_m = pd.to_datetime(df[time_col_multi].astype(str).str.replace('-', ':').str.replace(':', '-', 2), errors='coerce')
                    valid_ts_m = t_dates_m.dropna()
                    if not valid_ts_m.empty:
                        min_d_m, max_d_m = valid_ts_m.min().date(), valid_ts_m.max().date()
                        sel_date_m = st.date_input("Lọc theo ngày:", value=(min_d_m, max_d_m), min_value=min_d_m, max_value=max_d_m, key="date_multi")
                        start_d_m, end_d_m = (sel_date_m[0], sel_date_m[1]) if len(sel_date_m) == 2 else (sel_date_m[0], sel_date_m[0])

                res_choice_multi = st.selectbox(
                    "Làm mượt dữ liệu:", 
                    ["Nguyên bản", "Trung bình mỗi phút", "Trung bình mỗi 5 phút"], 
                    key="res_multi"
                )
                r_dict_multi = {"Nguyên bản": None, "Trung bình mỗi phút": "1min", "Trung bình mỗi 5 phút": "5min"}

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="btn_multi"):
                if len(selected_comparison_keys) < 2:
                    st.warning("Hãy chọn ít nhất 2 chỉ số!")
                else:
                    all_multi_points = []
                    working_df_multi = df.copy()
                    
                    if time_col_multi and start_d_m and end_d_m:
                        working_df_multi[time_col_multi] = pd.to_datetime(working_df_multi[time_col_multi].astype(str).str.replace('-', ':').str.replace(':', '-', 2), errors='coerce')
                        working_df_multi = working_df_multi.dropna(subset=[time_col_multi])
                        mask_m = (working_df_multi[time_col_multi].dt.date >= start_d_m) & (working_df_multi[time_col_multi].dt.date <= end_d_m)
                        working_df_multi = working_df_multi[mask_m]

                    for col in selected_comparison_keys:
                        # Tiếp tục áp dụng tính năng xử lý siêu tốc cho biểu đồ lồng nhau
                        extracted_series_m = working_df_multi.apply(lambda row: extract_points(row[col], row[time_col_multi], col_name=col), axis=1)
                        for pts in extracted_series_m:
                            if isinstance(pts, list):
                                all_multi_points.extend(pts)
                    
                    if all_multi_points:
                        multi_chart_df = pd.DataFrame(all_multi_points)
                        rule_multi = r_dict_multi[res_choice_multi]
                        
                        if start_d_m and end_d_m:
                            delta_days_m = (end_d_m - start_d_m).days
                            if delta_days_m > 7 and not rule_multi:
                                st.warning(f"⚠️ Khoảng thời gian so sánh quá dài ({delta_days_m} ngày). Hệ thống tự động chuyển sang 'Trung bình mỗi 5 phút' để biểu đồ hoạt động mượt mà.")
                                rule_multi = "5min"

                        if rule_multi:
                            plot_data_multi = multi_chart_df.set_index('TG').groupby('Loại chỉ số')['Giá trị'].resample(rule_multi).mean().dropna().reset_index()
                        else:
                            plot_data_multi = multi_chart_df.groupby(['TG', 'Loại chỉ số'])['Giá trị'].mean().reset_index()

                        if not plot_data_multi.empty:
                            plot_data_multi = plot_data_multi.sort_values(by='TG')
                            
                            st.write(f"### Biểu đồ đối chiếu giá trị thực")
                            
                            num_multi_points = len(plot_data_multi)
                            use_webgl_multi = 'webgl' if num_multi_points > 2000 else 'svg'
                            show_markers_multi = num_multi_points <= 1000

                            fig_multi = px.line(
                                plot_data_multi, 
                                x='TG', 
                                y='Giá trị', 
                                color='Loại chỉ số', 
                                markers=show_markers_multi,
                                render_mode=use_webgl_multi
                            )
                            
                            fig_multi.update_layout(
                                xaxis_title="Thời gian (TG)", 
                                yaxis_title="Giá trị (Đơn vị đo thực tế)",
                                hovermode="x unified", 
                                dragmode='pan',
                                xaxis=dict(rangeslider=dict(visible=False), type="date")
                            )
                            
                            fig_multi.update_xaxes(showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
                            fig_multi.update_yaxes(showspikes=True, spikecolor="gray", spikemode="across")
                            
                            st.plotly_chart(fig_multi, use_container_width=True, config={'scrollZoom': True})

                            with st.expander(f"Xem bảng dữ liệu ({num_multi_points} điểm)"):
                                st.dataframe(plot_data_multi, use_container_width=True)
                    else:
                        st.error("Không có dữ liệu hiển thị.")

    except Exception as e:
        st.error(f"Lỗi: {e}")
