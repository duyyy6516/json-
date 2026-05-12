# 👉 Dưới đây là các "Đồ nghề" (Thư viện) cần thiết để xây dựng ứng dụng
import streamlit as st       # 👉 Dùng để tạo giao diện Web cực nhanh
import pandas as pd          # 👉 Dùng để xử lý dữ liệu dạng bảng (giống Excel)
import numpy as np           # 👉 Dùng để tính toán số học và xử lý các ô trống
import json                  # 👉 Dùng để đọc hiểu file dữ liệu định dạng JSON
import re                    # 👉 Công cụ Regex: Dùng để tìm kiếm và cắt chữ siêu tốc
import plotly.express as px  # 👉 Họa sĩ: Dùng để vẽ biểu đồ tương tác cực đẹp
import io                    # 👉 Xử lý luồng dữ liệu đầu vào/ra

# ==============================================================================
# --- CẤU HÌNH TRANG & THÔNG SỐ TỐI ƯU ---
# ==============================================================================
# 👉 Thiết lập tab trên trình duyệt web: Tên tab, mở rộng toàn màn hình, và icon cái cây
st.set_page_config(page_title="JSON Data Pro", layout="wide", page_icon="🌱")
# 👉 In cái tiêu đề to đùng ra giữa màn hình
st.title("🌱 Công cụ Phân tích Dữ liệu Nông Nghiệp")

# 👉 Cuốn sổ ghi chép giới hạn an toàn của cây. Nếu máy đo ra số ngoài khoảng này -> Lỗi máy đo
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
# 1. CÁC HÀM XỬ LÝ LÕI (NHỮNG CÔNG NHÂN CHUYÊN XỬ LÝ DỮ LIỆU)
# ==============================================================================

@st.cache_data # 👉 Bùa ghi nhớ: Giúp máy tính nhớ kết quả hàm này, đỡ phải chạy lại từ đầu làm chậm web
def normalize_keys(data):
    # 👉 Hàm này làm sạch Tên cột: Xóa khoảng trắng thừa và viết thường hết cho đồng nhất
    if isinstance(data, list):
        return [normalize_keys(item) for item in data]
    elif isinstance(data, dict):
        return {str(k).strip().lower(): normalize_keys(v) for k, v in data.items()}
    return data

@st.cache_data
def flatten_json(y):
    # 👉 Hàm này giống như cái máy ép: Ép các dữ liệu lồng lộn xộn trong JSON thành 1 cái bảng ngang phẳng lì
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
    # 👉 Hàm tổng quản: Mở file JSON lên và biến nó thành Bảng Excel (DataFrame)
    try:
        raw_data = json.loads(file_bytes) # 👉 Đọc file
    except json.JSONDecodeError:
        raise ValueError("File tải lên không đúng định dạng JSON hợp lệ.")
        
    if isinstance(raw_data, dict): 
        raw_data = [raw_data] # 👉 Bọc dữ liệu lại nếu nó đứng 1 mình
    
    # 👉 Chuyển dữ liệu qua máy rửa (normalize) và máy ép (flatten)
    clean_json = normalize_keys(raw_data)
    df = pd.DataFrame([flatten_json(row) for row in clean_json])
    
    # 👉 Dọn dẹp rác: Xóa cột rỗng, xóa cột trùng lặp
    df = df.dropna(axis=1, how='all').loc[:, ~df.columns.duplicated()]
    df = df.replace(r'^\s*$', np.nan, regex=True) # 👉 Biến các ô chỉ có dấu cách thành ô rỗng (NaN)
    
    # 👉 Tự động đi tìm cột nào có chữ "time" hoặc "thời gian" để làm cột Mốc Thời Gian chính
    time_col = next((col for col in df.columns if 'time' in col.lower() or 'thời gian' in col.lower()), None)
    if time_col:
        # 👉 Sửa lỗi gõ sai ngày tháng (ví dụ 2023-10:25 thành đúng chuẩn đồng hồ)
        df['_parsed_time'] = pd.to_datetime(
            df[time_col].astype(str).str.replace('-', ':').str.replace(':', '-', 2), 
            errors='coerce'
        )
    return df, time_col

# ==============================================================================
# 2. CÁC HÀM TIỆN ÍCH CHO BIỂU ĐỒ & BỘ LỌC
# ==============================================================================

def render_date_filter(min_date, max_date, key_prefix):
    # 👉 Hàm tạo ra cái Lịch trên màn hình để người dùng chọn khoảng thời gian muốn xem
    if not min_date: return None, None
    
    # 👉 Tạo 4 nút bấm tròn (Radio) chọn kiểu xem
    mode = st.radio(
        "⏳ Kiểu lọc thời gian:", 
        ["Tùy chọn", "Theo Tuần (7 ngày)", "Theo Tháng", "Theo Quý"], 
        horizontal=True, 
        key=f"mode_{key_prefix}"
    )
    
    # 👉 Tính toán Ngày bắt đầu và Ngày kết thúc dựa vào kiểu xem user đã chọn
    if mode == "Tùy chọn":
        sel_date = st.date_input("📅 Chọn khoảng ngày:", value=(min_date, max_date), min_value=min_date, max_value=max_date, key=f"date_{key_prefix}")
        start_d = sel_date[0] if sel_date else None
        end_d = sel_date[1] if sel_date and len(sel_date) == 2 else start_d
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
    """
    👉 Hàm giải phẫu: Mổ xẻ những chuỗi đo đạc bị dính chùm vào nhau thành từng dòng rõ ràng
    Ví dụ: "20-11-18/0.26" sẽ được mổ ra thành -> Giờ: 20:11:18, Số liệu: 0.26
    """
    records = [] # 👉 Cái giỏ chứa dữ liệu sau khi mổ xẻ
    cols_to_extract = ['_parsed_time'] + selected_cols
    working_df = df[cols_to_extract].dropna(subset=['_parsed_time'])
    
    # 👉 Đọc qua từng dòng trong bảng dữ liệu
    for row in working_df.itertuples(index=False):
        main_time = row[0] # Lấy Mốc thời gian chính của dòng
        date_str = main_time.strftime('%Y-%m-%d') # Lấy ra cái Ngày
        
        # 👉 Kiểm tra từng cột cảm biến mà user đang muốn xem
        for i, col_name in enumerate(selected_cols, start=1):
            val = str(row[i]).strip()
            if not val or val.lower() == 'nan':
                continue # Dữ liệu rỗng thì bỏ qua
                
            col_upper = col_name.upper()
            
            # 👉 Hàm phụ: Sửa lỗi máy đo bị điên (ví dụ pH đo ra 689 thay vì 6.89 thì chia cho 100)
            def process_val(v_str):
                v = float(v_str)
                if col_upper in ['PH', 'TBPH'] and v > 14: return v / 100.0
                if col_upper in ['NHIỆT ĐỘ'] and v > 100: return v / 10.0
                return v
                
            # 👉 Ninja Regex: Chém chuỗi dính chùm ra. Tìm đúng mẫu "Giờ-phút-giây / Con số"
            matches = re.findall(r'(\d{2}-\d{2}-\d{2})/([-+]?\d*\.?\d+)', val)
            
            if matches:
                # Nếu tìm thấy dính chùm, tách nó ra và lưu vào giỏ
                for t_str, v_str in matches:
                    try:
                        full_t_str = f"{date_str} {t_str.replace('-', ':')}" # Ghép Ngày với Giờ
                        records.append({'TG': pd.to_datetime(full_t_str), 'Giá trị': process_val(v_str), 'Chỉ số': col_upper})
                    except Exception:
                        pass
            else:
                # Nếu là 1 con số bình thường đo 1 lần thì bốc luôn số đó
                num_match = re.search(r'[-+]?\d*\.?\d+', val)
                if num_match:
                    records.append({'TG': main_time, 'Giá trị': process_val(num_match.group()), 'Chỉ số': col_upper})
                    
    return pd.DataFrame(records) # Trả về 1 cái Bảng mới gọn gàng

def generate_chart(df, title, is_multi=False):
    # 👉 Họa sĩ vẽ đồ thị
    num_points = len(df)
    use_webgl = 'webgl' if num_points > 1000 else 'svg' # 👉 Dùng card đồ họa vẽ nếu số liệu quá nhiều để chống đơ máy
    show_markers = num_points <= 1000 # 👉 Ẩn dấu chấm tròn đi cho đỡ rối mắt nếu điểm quá nhiều
    
    # 👉 Vẽ line chart (biểu đồ đường)
    if is_multi:
        fig = px.line(df, x='TG', y='Giá trị', color='Chỉ số', markers=show_markers, render_mode=use_webgl,
                      color_discrete_sequence=px.colors.qualitative.Set1)
    else:
        fig = px.line(df, x='TG', y='Giá trị', markers=show_markers, render_mode=use_webgl)
        
    # 👉 Chỉnh trang nhan sắc cho biểu đồ (Thêm thanh gióng kẻ ngang, tắt thanh trượt cuộn)
    fig.update_layout(
        title=f"<b>{title}</b>", xaxis_title="Thời gian", yaxis_title="Giá trị",
        hovermode="x unified", dragmode='pan',
        xaxis=dict(rangeslider=dict(visible=False), type="date")
    )
    fig.update_xaxes(showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
    fig.update_yaxes(showspikes=True, spikecolor="gray", spikemode="across")
    return fig, num_points

# ==============================================================================
# 3. XỬ LÝ GIAO DIỆN & FILE UPLOAD (QUẦY LỄ TÂN)
# ==============================================================================

# 👉 Nút tải file ở chính giữa màn hình
uploaded_file = st.file_uploader("Tải lên file JSON", type=['json'])

if uploaded_file is not None:
    try:
        with st.spinner("Đang xử lý dữ liệu..."): # 👉 Hiển thị loading xoay xoay
            file_bytes = uploaded_file.getvalue().decode("utf-8")
            df, time_col = load_and_process_data(file_bytes) # Gọi ông tổng quản ra xử lý

        # --- THANH BỘ LỌC BÊN TRÁI MÀN HÌNH ---
        st.sidebar.markdown("### 🔍 BỘ LỌC TÙY CHỈNH")
        filterable_cols = [col for col in df.columns if col not in ['_parsed_time']] # Tìm các cột để tạo list lọc
        selected_key = st.sidebar.selectbox("1. Chọn trường dữ liệu (Key) muốn lọc:", options=["-- Không lọc --"] + filterable_cols)
        
        # Nếu user chọn lọc theo khu vực/trạng thái...
        if selected_key != "-- Không lọc --":
            unique_values = df[selected_key].dropna().astype(str).unique() # Tìm xem cột đó có những chữ gì đặc biệt
            list_values = ["Tất cả"] + list(unique_values)
            selected_value = st.sidebar.selectbox(f"2. Chọn giá trị cho '{selected_key.upper()}':", options=list_values)
            
            # Cắt bảng dữ liệu theo điều kiện user chọn
            if selected_value != "Tất cả":
                df = df[df[selected_key].astype(str) == selected_value].reset_index(drop=True)
                st.sidebar.success(f"✅ Đang lọc: {selected_key.upper()} = {selected_value}")
                if df.empty:
                    st.error("⚠️ Bộ lọc này không trả về kết quả nào. Vui lòng chọn giá trị khác!")
                    st.stop() # Dừng chạy toàn bộ code nếu không còn dữ liệu

        # 👉 Lọc ra tên các cột chứa số (Loại bỏ cột chữ như stt, tên người...) để làm nút check chọn vẽ
        exclude = [time_col, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển', '_parsed_time']
        numeric_options = [c for c in df.columns if c not in exclude and '_id' not in c]

        # 👉 Tìm cái Ngày nhỏ nhất và Lớn nhất trong file để làm mốc giới hạn cho cái Lịch
        min_d, max_d = None, None
        if '_parsed_time' in df.columns:
            valid_ts = df['_parsed_time'].dropna()
            if not valid_ts.empty:
                min_d, max_d = valid_ts.min().date(), valid_ts.max().date()

        st.markdown("---")
        
        # 👉 Chia giao diện thành 3 Tab chính cho dễ nhìn
        tab1, tab2, tab3 = st.tabs(["🗂️ Bảng dữ liệu", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau"])

        # ==========================================
        # TAB 1: BẢNG DỮ LIỆU
        # ==========================================
        with tab1:
            st.subheader("🌾 Bảng dữ liệu chi tiết")
            display_df = df.drop(columns=['_parsed_time'], errors='ignore').fillna("")
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.write(f"Đang hiển thị: **{len(df)}** bản ghi (dựa theo bộ lọc hiện tại)")
            with col_h2:
                # 👉 Biến bảng Dataframe thành file Excel CSV để user bấm nút tải về
                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Tải xuống CSV", data=csv, file_name='data_export.csv', mime='text/csv', use_container_width=True)
            st.dataframe(display_df, use_container_width=True) # 👉 In cái bảng ra màn hình

        # ==========================================
        # TAB 2: BIỂU ĐỒ ĐƠN LẺ
        # ==========================================
        with tab2:
            st.write("⚙️ Thiết lập biểu đồ đơn lẻ")
            col1, col2 = st.columns([1, 2])
            with col1:
                start_d_2, end_d_2 = render_date_filter(min_d, max_d, "tab2") # Chèn cái lịch vào Tab 2
                filter_data_2 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, key="filter_tab2")

            with col2:
                st.write("Chọn chỉ số:")
                cols_ui = st.columns(4) # Chia màn hình thành 4 cột nhỏ để gắn nút tick (checkbox)
                # 👉 Ghi sổ lại xem user đã tick vào ô nào (PH, EC, Nhiệt độ...)
                selected_keys_2 = [k for i, k in enumerate(numeric_options) if cols_ui[i % 4].checkbox(k.upper(), key=f"c_tab2_{k}")]

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="btn_tab2"):
                if not selected_keys_2:
                    st.warning("Hãy chọn ít nhất 1 chỉ số!")
                elif not start_d_2 or not end_d_2:
                    st.warning("Vui lòng chọn khoảng thời gian hợp lệ!")
                else:
                    # Cắt DataFrame theo ngày user đã chọn từ Lịch
                    mask = (df['_parsed_time'].dt.date >= start_d_2) & (df['_parsed_time'].dt.date <= end_d_2)
                    filtered_df = df[mask]
                    
                    # Gọi hàm giải phẫu mổ xẻ dữ liệu
                    chart_df = extract_sensor_data(filtered_df, selected_keys_2) 
                    
                    if not chart_df.empty:
                        # 👉 LOGIC ÉP BUỘC LÀM MƯỢT TRUNG BÌNH THEO NGÀY NẾU > 2 NGÀY
                        # Đếm xem user chọn bao nhiêu ngày. Nếu lớn hơn 2 ngày thì sẽ bật tính năng Gom nhóm (1D = 1 Day)
                        days_diff = (end_d_2 - start_d_2).days if (start_d_2 and end_d_2) else 0
                        rule = "1D" if days_diff > 2 else None

                        if rule == "1D":
                            st.info("💡 Do khoảng thời gian bạn chọn > 2 ngày, hệ thống đã ngầm tự động gộp và tính trung bình các số liệu theo từng ngày để biểu đồ trực quan, dễ nhìn hơn.")

                        # Tiến hành dọn dẹp và vẽ biểu đồ cho từng chỉ số được user chọn
                        for col in selected_keys_2:
                            sub_df = chart_df[chart_df['Chỉ số'] == col.upper()]
                            ten_chi_so = col.upper()
                            
                            # Nếu tick vào lọc nhiễu, đối chiếu với Cuốn Sổ KHOANG_TOI_UU ở trên cùng để xóa số ảo
                            if filter_data_2 and ten_chi_so in KHOANG_TOI_UU:
                                min_val, max_val = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_val) & (sub_df['Giá trị'] <= max_val)]
                            
                            if sub_df.empty: continue
                            
                            # 👉 Resample: Quá trình gom dữ liệu dính chùm cùng một ngày thành 1 điểm Trung Bình Cộng duy nhất
                            if rule: 
                                plot_data = sub_df.set_index('TG').resample(rule)['Giá trị'].mean().dropna().reset_index()
                            else: 
                                plot_data = sub_df.groupby('TG')['Giá trị'].mean().reset_index()
                                
                            plot_data = plot_data.sort_values(by='TG')
                            
                            # Gọi Họa sĩ ra vẽ biểu đồ
                            fig, pts = generate_chart(plot_data, f"Chỉ số: {ten_chi_so}", is_multi=False)
                            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                            
                            # In cái bảng số liệu đã vẽ ra thành dạng bảng cho user dễ đối chiếu (nhấn mở rộng để xem)
                            trang_thai_loc = "Đã lọc sạch" if filter_data_2 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu của biểu đồ trên để đối chứng ({pts} điểm - {trang_thai_loc})"):
                                st.dataframe(plot_data, use_container_width=True)
                            st.write("---")
                    else: st.info("Không có dữ liệu hợp lệ trong khoảng thời gian này.")

        # ==========================================
        # TAB 3: BIỂU ĐỒ LỒNG NHAU (GỘP CHUNG CHỈ SỐ)
        # ==========================================
        with tab3:
            # 👉 Cơ chế hoạt động của Tab 3 y chang Tab 2, chỉ khác ở bước cuối cùng thay vì vẽ từng hình, 
            # nó gom tất cả Data lại thành 1 cục (concat) rồi mới gọi Họa sĩ ra vẽ chung vào 1 biểu đồ.
            
            st.write("⚙️ Thiết lập biểu đồ lồng nhau")
            col1_m, col2_m = st.columns([1, 2])
            with col1_m:
                st.write("🎯 **Chọn chỉ số:**")
                check_multi_ui = st.columns(3)
                selected_keys_3 = [k for i, k in enumerate(numeric_options) if check_multi_ui[i % 3].checkbox(k.upper(), key=f"c_multi_{k}")]

            with col2_m:
                start_d_3, end_d_3 = render_date_filter(min_d, max_d, "tab3")
                filter_data_3 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, key="filter_tab3")

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="btn_multi"):
                if len(selected_keys_3) < 2:
                    st.warning("Hãy chọn ít nhất 2 chỉ số!")
                elif not start_d_3 or not end_d_3:
                    st.warning("Vui lòng chọn khoảng thời gian hợp lệ!")
                else:
                    mask = (df['_parsed_time'].dt.date >= start_d_3) & (df['_parsed_time'].dt.date <= end_d_3)
                    filtered_df = df[mask]
                    
                    multi_chart_df = extract_sensor_data(filtered_df, selected_keys_3) 
                    
                    if not multi_chart_df.empty:
                        days_diff = (end_d_3 - start_d_3).days if (start_d_3 and end_d_3) else 0
                        rule = "1D" if days_diff > 2 else None

                        if rule == "1D":
                            st.info("💡 Do khoảng thời gian bạn chọn > 2 ngày, hệ thống đã ngầm tự động gộp và tính trung bình các số liệu theo từng ngày để biểu đồ trực quan, dễ nhìn hơn.")

                        clean_dfs = [] # 👉 Tạo cái giỏ trống để nhét các data đã xử lý sạch sẽ vào
                        for col in selected_keys_3:
                            sub_df = multi_chart_df[multi_chart_df['Chỉ số'] == col.upper()]
                            ten_chi_so = col.upper()
                            
                            if filter_data_3 and ten_chi_so in KHOANG_TOI_UU:
                                min_val, max_val = KHOANG_TOI_UU[ten_chi_so]
                                sub_df = sub_df[(sub_df['Giá trị'] >= min_val) & (sub_df['Giá trị'] <= max_val)]
                                
                            if not sub_df.empty: clean_dfs.append(sub_df) # Lọc sạch xong thì nhét vô giỏ
                            
                        # 👉 pd.concat: Gom tất cả các Data trong giỏ thành 1 bảng to duy nhất
                        multi_chart_df = pd.concat(clean_dfs) if clean_dfs else pd.DataFrame()
                        
                        if not multi_chart_df.empty:
                            if rule: 
                                plot_data = multi_chart_df.set_index('TG').groupby('Chỉ số')['Giá trị'].resample(rule).mean().dropna().reset_index()
                            else: 
                                plot_data = multi_chart_df.groupby(['TG', 'Chỉ số'])['Giá trị'].mean().reset_index()
                                
                            plot_data = plot_data.sort_values(by='TG')
                            
                            fig, pts = generate_chart(plot_data, f"Biểu đồ Đối chiếu Trực tiếp", is_multi=True) # 👉 Báo họa sĩ vẽ chung is_multi=True
                            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                            
                            trang_thai_loc_3 = "Đã lọc sạch" if filter_data_3 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu gộp của biểu đồ trên để đối chứng ({pts} điểm - {trang_thai_loc_3})"):
                                # 👉 Pivot Table: Thay vì kéo dài bảng xuống 10.000 dòng, Pivot dàn bảng thành dạng ngang (Mỗi chỉ số 1 cột) cho dễ so sánh
                                pivot_df = plot_data.pivot(index='TG', columns='Chỉ số', values='Giá trị').reset_index()
                                st.dataframe(pivot_df, use_container_width=True)
                    else: st.info("Không có dữ liệu hợp lệ trong khoảng thời gian này.")

    # 👉 Cái rào chắn cuối cùng: Bắt mọi thể loại lỗi hệ thống phát sinh để App không bị sập màn hình trắng
    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
