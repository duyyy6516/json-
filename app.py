import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import plotly.express as px
import io

# ==============================================================================
# KHU VỰC 1: CẤU HÌNH TRANG WEB & THÔNG SỐ CƠ BẢN
# ==============================================================================
# 👉 Thiết lập tiêu đề trang trên tab trình duyệt
st.set_page_config(page_title="JSON Data Pro", layout="wide", page_icon="🌱")
st.title("🌱 Công cụ Phân tích Dữ liệu Nông Nghiệp (Bản Dễ Hiểu)")

# 👉 Cuốn sổ ghi chép các giới hạn an toàn của cây trồng (Dùng để lọc dữ liệu lỗi)
GIOI_HAN_HOP_LY = {
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
# KHU VỰC 2: CÁC CÔNG NHÂN XỬ LÝ DỮ LIỆU (HÀM)
# ==============================================================================

@st.cache_data
def lam_sach_ten_cot(du_lieu):
    """Công nhân 1: Xóa khoảng trắng và biến mọi chữ thành in thường để đồng nhất"""
    if isinstance(du_lieu, list):
        danh_sach_moi = []
        for mon_do in du_lieu:
            danh_sach_moi.append(lam_sach_ten_cot(mon_do))
        return danh_sach_moi
        
    elif isinstance(du_lieu, dict):
        tu_dien_moi = {}
        for khoa, gia_tri in du_lieu.items():
            khoa_chu_thuong = str(khoa).strip().lower()
            tu_dien_moi[khoa_chu_thuong] = lam_sach_ten_cot(gia_tri)
        return tu_dien_moi
        
    return du_lieu

@st.cache_data
def lam_phang_du_lieu_json(du_lieu_json):
    """Công nhân 2: Ép các dữ liệu lồng ghép phức tạp thành 1 hàng ngang duy nhất"""
    du_lieu_da_phang = {}
    
    def ep_phang(thong_tin, ten_chuoi=''):
        if isinstance(thong_tin, dict):
            for khoa in thong_tin:
                ep_phang(thong_tin[khoa], ten_chuoi + khoa + '.')
        elif isinstance(thong_tin, list):
            for vi_tri, gia_tri in enumerate(thong_tin):
                ep_phang(gia_tri, ten_chuoi + str(vi_tri) + '.')
        else:
            du_lieu_da_phang[ten_chuoi[:-1]] = thong_tin
            
    ep_phang(du_lieu_json)
    return du_lieu_da_phang

@st.cache_data
def doc_va_xu_ly_file(file_tai_len):
    """Công nhân 3: Đọc file người dùng tải lên và hô biến thành Bảng Excel (DataFrame)"""
    try:
        du_lieu_goc = json.loads(file_tai_len)
    except Exception:
        raise ValueError("File tải lên không đúng định dạng JSON hợp lệ.")
        
    # Nếu dữ liệu chỉ có 1 món, ta bọc nó vào một danh sách để dễ xử lý
    if isinstance(du_lieu_goc, dict): 
        du_lieu_goc = [du_lieu_goc]
    
    du_lieu_sach_ten = lam_sach_ten_cot(du_lieu_goc)
    
    # Tạo bảng từ dữ liệu đã ép phẳng
    danh_sach_cac_hang = []
    for hang in du_lieu_sach_ten:
        danh_sach_cac_hang.append(lam_phang_du_lieu_json(hang))
        
    bang_du_lieu = pd.DataFrame(danh_sach_cac_hang)
    
    # Dọn dẹp bảng: Xóa cột trống rỗng, xóa cột trùng, xóa ô chỉ có dấu cách
    bang_du_lieu = bang_du_lieu.dropna(axis=1, how='all')
    bang_du_lieu = bang_du_lieu.loc[:, ~bang_du_lieu.columns.duplicated()]
    bang_du_lieu = bang_du_lieu.replace(r'^\s*$', np.nan, regex=True)
    
    # Tìm xem cột nào đang chứa từ "time" hoặc "thời gian"
    ten_cot_thoi_gian = None
    for cot in bang_du_lieu.columns:
        if 'time' in cot.lower() or 'thời gian' in cot.lower():
            ten_cot_thoi_gian = cot
            break
            
    # Chỉnh đốn lại cột thời gian cho đúng chuẩn máy tính hiểu
    if ten_cot_thoi_gian:
        cot_thoi_gian_tam_thoi = bang_du_lieu[ten_cot_thoi_gian].astype(str)
        cot_thoi_gian_tam_thoi = cot_thoi_gian_tam_thoi.str.replace('-', ':')
        cot_thoi_gian_tam_thoi = cot_thoi_gian_tam_thoi.str.replace(':', '-', 2)
        bang_du_lieu['Thoi_Gian_Chuan'] = pd.to_datetime(cot_thoi_gian_tam_thoi, errors='coerce')
        
    return bang_du_lieu, ten_cot_thoi_gian

def tao_bo_loc_thoi_gian(ngay_nho_nhat, ngay_lon_nhat, ma_so_tab):
    """Công nhân 4: Tạo ra cái thanh chọn ngày tháng trên màn hình"""
    if not ngay_nho_nhat: return None, None
    
    kieu_loc = st.radio(
        "⏳ Kiểu lọc thời gian:", 
        ["Tùy chọn", "Theo Tuần (7 ngày)", "Theo Tháng", "Theo Quý"], 
        horizontal=True, 
        key=f"che_do_{ma_so_tab}"
    )
    
    if kieu_loc == "Tùy chọn":
        ngay_duoc_chon = st.date_input("📅 Chọn khoảng ngày:", value=(ngay_nho_nhat, ngay_lon_nhat), min_value=ngay_nho_nhat, max_value=ngay_lon_nhat, key=f"ngay_{ma_so_tab}")
        ngay_bat_dau = ngay_duoc_chon[0] if ngay_duoc_chon else None
        
        # Nếu người dùng chọn 2 ngày (từ ngày - đến ngày)
        if ngay_duoc_chon and len(ngay_duoc_chon) == 2:
            ngay_ket_thuc = ngay_duoc_chon[1]
        else:
            ngay_ket_thuc = ngay_bat_dau
    else:
        ngay_bat_dau = st.date_input("📅 Chọn ngày bắt đầu:", value=ngay_nho_nhat, min_value=ngay_nho_nhat, max_value=ngay_lon_nhat, key=f"ngay_bat_dau_{ma_so_tab}")
        if ngay_bat_dau:
            ngay_bat_dau_he_thong = pd.to_datetime(ngay_bat_dau)
            
            if kieu_loc == "Theo Tuần (7 ngày)":
                ngay_ket_thuc = (ngay_bat_dau_he_thong + pd.Timedelta(days=6)).date()
            elif kieu_loc == "Theo Tháng":
                ngay_ket_thuc = (ngay_bat_dau_he_thong + pd.DateOffset(months=1) - pd.Timedelta(days=1)).date()
            elif kieu_loc == "Theo Quý":
                ngay_ket_thuc = (ngay_bat_dau_he_thong + pd.DateOffset(months=3) - pd.Timedelta(days=1)).date()
            
            if ngay_ket_thuc > ngay_lon_nhat:
                ngay_ket_thuc = ngay_lon_nhat
            
            st.success(f"🎯 Sẽ lọc từ: **{ngay_bat_dau.strftime('%d/%m/%Y')}** đến **{ngay_ket_thuc.strftime('%d/%m/%Y')}**")
        else:
            ngay_ket_thuc = None
            
    return ngay_bat_dau, ngay_ket_thuc

def boc_tach_du_lieu_cam_bien(bang_du_lieu, danh_sach_cot_muon_lay):
    """Công nhân 5: Chuyên gia giải phẫu, mổ xẻ những chuỗi đo đạc bị dính chùm vào nhau"""
    gio_chua_du_lieu_sach = []
    cac_cot_do_lien_tuc = set() # Ghi nhớ xem cột nào đo đạc dày đặc (có nhiều thời gian trong 1 ô)
    
    # Chỉ giữ lại cột Thời Gian và các cột Cảm biến người dùng chọn
    cac_cot_can_thiet = ['Thoi_Gian_Chuan'] + danh_sach_cot_muon_lay
    bang_du_lieu_dang_xu_ly = bang_du_lieu[cac_cot_can_thiet].dropna(subset=['Thoi_Gian_Chuan'])
    
    # Hàm con: Xử lý giá trị lỗi của cảm biến (Ví dụ cảm biến pH ghi nhầm 689 thay vì 6.89)
    def sua_loi_con_so(chuoi_so, ten_cot):
        con_so = float(chuoi_so)
        if ten_cot in ['PH', 'TBPH'] and con_so > 14: 
            return con_so / 100.0
        if ten_cot in ['NHIỆT ĐỘ'] and con_so > 100: 
            return con_so / 10.0
        return con_so

    # Đọc qua từng hàng trong bảng
    for vi_tri, hang in bang_du_lieu_dang_xu_ly.iterrows():
        thoi_gian_chinh = hang['Thoi_Gian_Chuan']
        chuoi_ngay_thang = thoi_gian_chinh.strftime('%Y-%m-%d')
        
        # Đọc từng ô cảm biến trong hàng đó
        for ten_cot in danh_sach_cot_muon_lay:
            gia_tri_o = str(hang[ten_cot]).strip()
            
            # Nếu ô trống thì bỏ qua
            if gia_tri_o == "" or gia_tri_o.lower() == 'nan':
                continue
                
            ten_cot_viet_hoa = ten_cot.upper()
            
            # Tìm xem có chuỗi nào dạng "Giờ-Phút-Giây/Con-số" không
            mau_tim_kiem = r'(\d{2}-\d{2}-\d{2})/([-+]?\d*\.?\d+)'
            ket_qua_tim_thay = re.findall(mau_tim_kiem, gia_tri_o)
            
            if len(ket_qua_tim_thay) > 0:
                cac_cot_do_lien_tuc.add(ten_cot_viet_hoa) # Ghi sổ: Cột này đo rất dày đặc
                
                # Tách từng cặp Giờ và Giá Trị ra
                for chuoi_gio, chuoi_gia_tri in ket_qua_tim_thay:
                    try:
                        gio_phut_giay = chuoi_gio.replace('-', ':')
                        thoi_gian_hoan_chinh = f"{chuoi_ngay_thang} {gio_phut_giay}"
                        
                        dong_moi = {
                            'TG': pd.to_datetime(thoi_gian_hoan_chinh), 
                            'Giá trị': sua_loi_con_so(chuoi_gia_tri, ten_cot_viet_hoa), 
                            'Chỉ số': ten_cot_viet_hoa
                        }
                        gio_chua_du_lieu_sach.append(dong_moi)
                    except Exception:
                        pass # Nếu lỗi thì âm thầm bỏ qua
            else:
                # Nếu không bị dính chùm, tìm 1 con số bình thường trong ô đó
                con_so_don_le = re.search(r'[-+]?\d*\.?\d+', gia_tri_o)
                if con_so_don_le:
                    dong_moi = {
                        'TG': thoi_gian_chinh, 
                        'Giá trị': sua_loi_con_so(con_so_don_le.group(), ten_cot_viet_hoa), 
                        'Chỉ số': ten_cot_viet_hoa
                    }
                    gio_chua_du_lieu_sach.append(dong_moi)
                    
    # Lấy dữ liệu từ giỏ ra, đóng thành bảng
    bang_da_boc_tach = pd.DataFrame(gio_chua_du_lieu_sach)
    return bang_da_boc_tach, cac_cot_do_lien_tuc

def ve_bieu_do_plotly(bang_du_lieu, tieu_de, ve_nhieu_duong=False):
    """Công nhân 6: Họa sĩ vẽ biểu đồ tương tác"""
    so_luong_diem = len(bang_du_lieu)
    
    # Nếu nhiều hơn 1000 điểm thì dùng webgl (nhờ card đồ họa vẽ cho đỡ giật máy)
    if so_luong_diem > 1000:
        che_do_ve = 'webgl'
        hien_thi_cham_tron = False # Ẩn chấm tròn đi cho đỡ rối mắt
    else:
        che_do_ve = 'svg'
        hien_thi_cham_tron = True
        
    if ve_nhieu_duong == True:
        bieu_do = px.line(bang_du_lieu, x='TG', y='Giá trị', color='Chỉ số', markers=hien_thi_cham_tron, render_mode=che_do_ve, color_discrete_sequence=px.colors.qualitative.Set1)
    else:
        bieu_do = px.line(bang_du_lieu, x='TG', y='Giá trị', markers=hien_thi_cham_tron, render_mode=che_do_ve)
        
    # Làm đẹp giao diện biểu đồ
    bieu_do.update_layout(
        title=f"<b>{tieu_de}</b>", xaxis_title="Thời gian", yaxis_title="Giá trị",
        hovermode="x unified", dragmode='pan',
        xaxis=dict(rangeslider=dict(visible=False), type="date")
    )
    bieu_do.update_xaxes(showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
    bieu_do.update_yaxes(showspikes=True, spikecolor="gray", spikemode="across")
    
    return bieu_do, so_luong_diem

# ==============================================================================
# KHU VỰC 3: GIAO DIỆN NGƯỜI DÙNG CHÍNH (QUẦY LỄ TÂN)
# ==============================================================================

nut_tai_file = st.file_uploader("Tải lên file JSON", type=['json'])

if nut_tai_file is not None:
    try:
        with st.spinner("Đang xử lý dữ liệu... Xin đợi một lát..."):
            noi_dung_file = nut_tai_file.getvalue().decode("utf-8")
            bang_du_lieu, cot_thoi_gian_goc = doc_va_xu_ly_file(noi_dung_file)

        # -----------------------------------------------------------------
        # THANH TRƯỢT BÊN TRÁI (BỘ LỌC)
        # -----------------------------------------------------------------
        st.sidebar.markdown("### 🔍 BỘ LỌC TÙY CHỈNH")
        
        # Tạo danh sách các cột có thể lọc (loại trừ cột thời gian do máy tính tự tạo)
        danh_sach_cot_loc = []
        for cot in bang_du_lieu.columns:
            if cot != 'Thoi_Gian_Chuan':
                danh_sach_cot_loc.append(cot)
                
        cot_muon_loc = st.sidebar.selectbox("1. Chọn trường dữ liệu (Key) muốn lọc:", options=["-- Không lọc --"] + danh_sach_cot_loc)
        
        if cot_muon_loc != "-- Không lọc --":
            # Lấy các giá trị không trùng lặp trong cột đó để tạo menu sổ xuống số 2
            cac_gia_tri_doc_nhat = bang_du_lieu[cot_muon_loc].dropna().astype(str).unique()
            danh_sach_lua_chon = ["Tất cả"] + list(cac_gia_tri_doc_nhat)
            gia_tri_muon_loc = st.sidebar.selectbox(f"2. Chọn giá trị cho '{cot_muon_loc.upper()}':", options=danh_sach_lua_chon)
            
            if gia_tri_muon_loc != "Tất cả":
                # Lọc bảng dữ liệu theo điều kiện người dùng chọn
                dieu_kien = bang_du_lieu[cot_muon_loc].astype(str) == gia_tri_muon_loc
                bang_du_lieu = bang_du_lieu[dieu_kien].reset_index(drop=True)
                
                st.sidebar.success(f"✅ Đang lọc: {cot_muon_loc.upper()} = {gia_tri_muon_loc}")
                
                if bang_du_lieu.empty:
                    st.error("⚠️ Bộ lọc này không trả về kết quả nào. Vui lòng chọn giá trị khác!")
                    st.stop() # Dừng chạy các code bên dưới

        # Chuẩn bị danh sách các cột chứa số liệu cảm biến (Loại bỏ các cột chữ như tên khu, người điều khiển...)
        cac_cot_bo_qua = [cot_thoi_gian_goc, 'stt', 'tên khu', 'trạng thái', 'phương thức hoạt động', 'người điều khiển', 'Thoi_Gian_Chuan']
        danh_sach_cot_cam_bien = []
        for cot in bang_du_lieu.columns:
            if cot not in cac_cot_bo_qua and '_id' not in cot:
                danh_sach_cot_cam_bien.append(cot)

        # Tìm Ngày cũ nhất và Ngày mới nhất trong toàn bộ dữ liệu
        ngay_nho_nhat = None
        ngay_lon_nhat = None
        if 'Thoi_Gian_Chuan' in bang_du_lieu.columns:
            cac_ngay_hop_le = bang_du_lieu['Thoi_Gian_Chuan'].dropna()
            if not cac_ngay_hop_le.empty:
                ngay_nho_nhat = cac_ngay_hop_le.min().date()
                ngay_lon_nhat = cac_ngay_hop_le.max().date()

        st.markdown("---")
        
        # -----------------------------------------------------------------
        # HIỂN THỊ 3 TAB CHÍNH
        # -----------------------------------------------------------------
        tab_bang, tab_bieu_do_don, tab_bieu_do_gop = st.tabs(["🗂️ Bảng dữ liệu", "📈 Biểu đồ Đơn", "📊 Biểu đồ Lồng nhau"])

        # ====== TAB 1: BẢNG DỮ LIỆU ======
        with tab_bang:
            st.subheader("🌾 Bảng dữ liệu chi tiết")
            bang_hien_thi = bang_du_lieu.drop(columns=['Thoi_Gian_Chuan'], errors='ignore').fillna("")
            
            cot_trai, cot_phai = st.columns([3, 1])
            with cot_trai:
                st.write(f"Đang hiển thị: **{len(bang_du_lieu)}** bản ghi (dựa theo bộ lọc hiện tại)")
            with cot_phai:
                file_csv = bang_hien_thi.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Tải xuống CSV", data=file_csv, file_name='du_lieu_nong_nghiep.csv', mime='text/csv', use_container_width=True)
                
            st.dataframe(bang_hien_thi, use_container_width=True)

        # ====== TAB 2: BIỂU ĐỒ ĐƠN LẺ ======
        with tab_bieu_do_don:
            st.write("⚙️ Thiết lập biểu đồ đơn lẻ")
            cot_trai_2, cot_phai_2 = st.columns([1, 2])
            
            with cot_trai_2:
                ngay_bat_dau_2, ngay_ket_thuc_2 = tao_bo_loc_thoi_gian(ngay_nho_nhat, ngay_lon_nhat, "tab2")
                chi_lay_du_lieu_sach_2 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, key="loc_rac_tab2")

            with cot_phai_2:
                st.write("Chọn chỉ số:")
                cac_cot_checkbox = st.columns(4)
                
                # Tạo danh sách ghi nhận người dùng đã tick chọn ô nào
                cac_chi_so_duoc_chon_2 = []
                for vi_tri, ten_cot in enumerate(danh_sach_cot_cam_bien):
                    # Rải đều các checkbox ra 4 cột
                    neu_duoc_tick = cac_cot_checkbox[vi_tri % 4].checkbox(ten_cot.upper(), key=f"checkbox_tab2_{ten_cot}")
                    if neu_duoc_tick:
                        cac_chi_so_duoc_chon_2.append(ten_cot)

            if st.button("🚀 TẠO BIỂU ĐỒ ĐƠN", type="primary", key="nut_bam_tab2"):
                if len(cac_chi_so_duoc_chon_2) == 0:
                    st.warning("Hãy chọn ít nhất 1 chỉ số!")
                elif not ngay_bat_dau_2 or not ngay_ket_thuc_2:
                    st.warning("Vui lòng chọn khoảng thời gian hợp lệ!")
                else:
                    # Cắt lấy đoạn dữ liệu theo ngày người dùng chọn
                    dieu_kien_ngay = (bang_du_lieu['Thoi_Gian_Chuan'].dt.date >= ngay_bat_dau_2) & (bang_du_lieu['Thoi_Gian_Chuan'].dt.date <= ngay_ket_thuc_2)
                    bang_da_cat_theo_ngay = bang_du_lieu[dieu_kien_ngay]
                    
                    # Gọi chuyên gia bóc tách dữ liệu
                    bang_bieu_do, danh_sach_do_lien_tuc = boc_tach_du_lieu_cam_bien(bang_da_cat_theo_ngay, cac_chi_so_duoc_chon_2) 
                    
                    if not bang_bieu_do.empty:
                        # Tính xem khoảng thời gian chọn là bao nhiêu ngày
                        so_ngay_chon = (ngay_ket_thuc_2 - ngay_bat_dau_2).days if (ngay_bat_dau_2 and ngay_ket_thuc_2) else 0

                        # Kiểm tra xem có cột nào người dùng chọn thuộc loại đo quá dày đặc không
                        cac_cot_day_dac_duoc_chon = []
                        for cot in cac_chi_so_duoc_chon_2:
                            if cot.upper() in danh_sach_do_lien_tuc:
                                cac_cot_day_dac_duoc_chon.append(cot.upper())
                                
                        if so_ngay_chon > 2 and len(cac_cot_day_dac_duoc_chon) > 0:
                            st.info(f"💡 Chỉ số ({', '.join(cac_cot_day_dac_duoc_chon)}) có tần suất quá dày, hệ thống ngầm gộp trung bình theo ngày cho dễ nhìn.")

                        # Xử lý và vẽ biểu đồ cho từng chỉ số
                        for chi_so in cac_chi_so_duoc_chon_2:
                            chi_so_viet_hoa = chi_so.upper()
                            bang_tam_thoi = bang_bieu_do[bang_bieu_do['Chỉ số'] == chi_so_viet_hoa]
                            
                            # Lọc loại bỏ dữ liệu bất thường (Nếu người dùng tick chọn)
                            if chi_lay_du_lieu_sach_2 and chi_so_viet_hoa in GIOI_HAN_HOP_LY:
                                gioi_han_duoi, gioi_han_tren = GIOI_HAN_HOP_LY[chi_so_viet_hoa]
                                bang_tam_thoi = bang_tam_thoi[(bang_tam_thoi['Giá trị'] >= gioi_han_duoi) & (bang_tam_thoi['Giá trị'] <= gioi_han_tren)]
                            
                            if bang_tam_thoi.empty: 
                                continue
                            
                            # CÔNG THỨC ÉP TRUNG BÌNH: Nếu xem trên 2 ngày VÀ chỉ số này thuộc nhóm đo liên tục
                            if so_ngay_chon > 2 and chi_so_viet_hoa in danh_sach_do_lien_tuc:
                                kieu_gop_du_lieu = "1D" # Gom trung bình cộng theo ngày (1 Day)
                            else:
                                kieu_gop_du_lieu = None # Để nguyên bản gốc
                                
                            if kieu_gop_du_lieu != None: 
                                du_lieu_de_ve = bang_tam_thoi.set_index('TG').resample(kieu_gop_du_lieu)['Giá trị'].mean().dropna().reset_index()
                            else: 
                                du_lieu_de_ve = bang_tam_thoi.groupby('TG')['Giá trị'].mean().reset_index()
                                
                            du_lieu_de_ve = du_lieu_de_ve.sort_values(by='TG')
                            
                            # Kêu họa sĩ vẽ biểu đồ
                            bieu_do, so_diem = ve_bieu_do_plotly(du_lieu_de_ve, f"Chỉ số: {chi_so_viet_hoa}", ve_nhieu_duong=False)
                            st.plotly_chart(bieu_do, use_container_width=True, config={'scrollZoom': True})
                            
                            trang_thai = "Đã lọc sạch nhiễu" if chi_lay_du_lieu_sach_2 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu của biểu đồ trên ({so_diem} điểm đo - {trang_thai})"):
                                st.dataframe(du_lieu_de_ve, use_container_width=True)
                            st.write("---")
                    else: 
                        st.info("Không có dữ liệu hợp lệ trong khoảng thời gian này.")

        # ====== TAB 3: BIỂU ĐỒ LỒNG NHAU ======
        with tab_bieu_do_gop:
            st.write("⚙️ Thiết lập biểu đồ lồng nhau")
            cot_trai_3, cot_phai_3 = st.columns([1, 2])
            
            with cot_trai_3:
                st.write("🎯 **Chọn ít nhất 2 chỉ số:**")
                cac_cot_checkbox_3 = st.columns(3)
                
                cac_chi_so_duoc_chon_3 = []
                for vi_tri, ten_cot in enumerate(danh_sach_cot_cam_bien):
                    neu_duoc_tick = cac_cot_checkbox_3[vi_tri % 3].checkbox(ten_cot.upper(), key=f"checkbox_tab3_{ten_cot}")
                    if neu_duoc_tick:
                        cac_chi_so_duoc_chon_3.append(ten_cot)

            with cot_phai_3:
                ngay_bat_dau_3, ngay_ket_thuc_3 = tao_bo_loc_thoi_gian(ngay_nho_nhat, ngay_lon_nhat, "tab3")
                chi_lay_du_lieu_sach_3 = st.checkbox("✅ Chỉ lấy dữ liệu Sạch (Bỏ nhiễu/lỗi)", value=True, key="loc_rac_tab3")

            if st.button("🚀 TẠO BIỂU ĐỒ ĐỐI CHIẾU", type="primary", key="nut_bam_tab3"):
                if len(cac_chi_so_duoc_chon_3) < 2:
                    st.warning("Hãy chọn ít nhất 2 chỉ số để so sánh!")
                elif not ngay_bat_dau_3 or not ngay_ket_thuc_3:
                    st.warning("Vui lòng chọn khoảng thời gian hợp lệ!")
                else:
                    dieu_kien_ngay_3 = (bang_du_lieu['Thoi_Gian_Chuan'].dt.date >= ngay_bat_dau_3) & (bang_du_lieu['Thoi_Gian_Chuan'].dt.date <= ngay_ket_thuc_3)
                    bang_da_cat_theo_ngay_3 = bang_du_lieu[dieu_kien_ngay_3]
                    
                    bang_bieu_do_3, danh_sach_do_lien_tuc_3 = boc_tach_du_lieu_cam_bien(bang_da_cat_theo_ngay_3, cac_chi_so_duoc_chon_3) 
                    
                    if not bang_bieu_do_3.empty:
                        so_ngay_chon_3 = (ngay_ket_thuc_3 - ngay_bat_dau_3).days if (ngay_bat_dau_3 and ngay_ket_thuc_3) else 0

                        cac_cot_day_dac_duoc_chon_3 = []
                        for cot in cac_chi_so_duoc_chon_3:
                            if cot.upper() in danh_sach_do_lien_tuc_3:
                                cac_cot_day_dac_duoc_chon_3.append(cot.upper())
                                
                        if so_ngay_chon_3 > 2 and len(cac_cot_day_dac_duoc_chon_3) > 0:
                            st.info(f"💡 Chỉ số ({', '.join(cac_cot_day_dac_duoc_chon_3)}) có tần suất quá dày, hệ thống ngầm gộp trung bình theo ngày.")

                        gio_chua_cac_bang_da_sach = []
                        for chi_so in cac_chi_so_duoc_chon_3:
                            chi_so_viet_hoa = chi_so.upper()
                            bang_tam_thoi = bang_bieu_do_3[bang_bieu_do_3['Chỉ số'] == chi_so_viet_hoa]
                            
                            if chi_lay_du_lieu_sach_3 and chi_so_viet_hoa in GIOI_HAN_HOP_LY:
                                gioi_han_duoi, gioi_han_tren = GIOI_HAN_HOP_LY[chi_so_viet_hoa]
                                bang_tam_thoi = bang_tam_thoi[(bang_tam_thoi['Giá trị'] >= gioi_han_duoi) & (bang_tam_thoi['Giá trị'] <= gioi_han_tren)]
                                
                            if so_ngay_chon_3 > 2 and chi_so_viet_hoa in danh_sach_do_lien_tuc_3:
                                kieu_gop_du_lieu = "1D" 
                            else:
                                kieu_gop_du_lieu = None
                                
                            if not bang_tam_thoi.empty:
                                if kieu_gop_du_lieu != None: 
                                    du_lieu_de_ve = bang_tam_thoi.set_index('TG').resample(kieu_gop_du_lieu)['Giá trị'].mean().dropna().reset_index()
                                else: 
                                    du_lieu_de_ve = bang_tam_thoi.groupby('TG')['Giá trị'].mean().reset_index()
                                
                                # Gắn mác tên chỉ số lại sau khi gom để chuẩn bị nhét chung vào 1 biểu đồ
                                du_lieu_de_ve['Chỉ số'] = chi_so_viet_hoa
                                gio_chua_cac_bang_da_sach.append(du_lieu_de_ve)
                            
                        # Ghép tất cả các bảng nhỏ thành 1 bảng to duy nhất
                        if len(gio_chua_cac_bang_da_sach) > 0:
                            bang_gop_tong = pd.concat(gio_chua_cac_bang_da_sach)
                        else:
                            bang_gop_tong = pd.DataFrame()
                        
                        if not bang_gop_tong.empty:
                            bang_gop_tong = bang_gop_tong.sort_values(by='TG')
                            
                            bieu_do_3, so_diem_3 = ve_bieu_do_plotly(bang_gop_tong, "Biểu đồ Đối chiếu Trực tiếp", ve_nhieu_duong=True)
                            st.plotly_chart(bieu_do_3, use_container_width=True, config={'scrollZoom': True})
                            
                            trang_thai_3 = "Đã lọc sạch" if chi_lay_du_lieu_sach_3 else "Chưa lọc - Gốc 100%"
                            with st.expander(f"📋 Bảng số liệu gộp ({so_diem_3} điểm - {trang_thai_3})"):
                                # Dàn ngang bảng ra cho người dùng dễ nhìn so sánh (Pivot Table)
                                bang_dan_ngang = bang_gop_tong.pivot(index='TG', columns='Chỉ số', values='Giá trị').reset_index()
                                st.dataframe(bang_dan_ngang, use_container_width=True)
                    else: 
                        st.info("Không có dữ liệu hợp lệ trong khoảng thời gian này.")

    except Exception as loi_he_thong:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {loi_he_thong}")
