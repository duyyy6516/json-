import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="JSON to Excel Tool", layout="wide")

st.title("📊 Công cụ Quản lý và Lọc Dữ liệu JSON")

# 1. Tải file lên
uploaded_file = st.file_uploader("Tải lên file JSON", type=["json"])

if uploaded_file is not None:
    try:
        # Đọc dữ liệu
        data = pd.read_json(uploaded_file)

        # Xử lý trường _id nếu là định dạng MongoDB
        if '_id' in data.columns:
            data['_id'] = data['_id'].apply(lambda x: x['$oid'] if isinstance(x, dict) and '$oid' in x else str(x))

        # --- BƯỚC CHUẨN HÓA TÊN CỘT ĐỂ TRÁNH TRÙNG LẶP ---
        def clean_column_name(col):
            col = str(col).strip()
            if len(col) > 0:
                # Viết hoa chữ cái đầu
                return col[0].upper() + col[1:]
            return col

        # Áp dụng đổi tên cột
        data.columns = [clean_column_name(c) for c in data.columns]

        # SỬA LỖI GỘP CỘT TẠI ĐÂY (Tương thích với Pandas mới nhất)
        new_data_dict = {}
        for col_name in data.columns.unique():
            col_data = data[col_name]
            if isinstance(col_data, pd.DataFrame): 
                # Nếu có từ 2 cột trở lên trùng tên, gộp dữ liệu lại (dồn ô trống)
                new_data_dict[col_name] = col_data.bfill(axis=1).iloc[:, 0]
            else:
                new_data_dict[col_name] = col_data
        
        # Tạo lại bảng dữ liệu sau khi đã gộp cột thành công
        data = pd.DataFrame(new_data_dict)
        # --------------------------------------------------------

        # ---------------------------------------------------------
        # BƯỚC 1: HIỆN FULL DỮ LIỆU TRƯỚC
        # ---------------------------------------------------------
        st.subheader("📋 Toàn bộ dữ liệu gốc (Đã được chuẩn hóa)")
        st.write(f"Tổng cộng có **{len(data)}** dòng dữ liệu.")
        st.dataframe(data, use_container_width=True)

        st.divider()

        # ---------------------------------------------------------
        # BƯỚC 2: CHỨC NĂNG LỌC (HIỆN SAU)
        # ---------------------------------------------------------
        st.subheader("🔍 Bộ lọc tùy chỉnh")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Chọn Key (Cột)
            all_columns = data.columns.tolist()
            selected_column = st.selectbox("1. Chọn cột muốn lọc:", all_columns)

        with col2:
            # Chọn giá trị trong Key đó (loại bỏ các giá trị trống để danh sách đẹp hơn)
            unique_values = data[selected_column].dropna().unique().tolist()
            selected_values = st.multiselect(
                f"2. Chọn giá trị trong '{selected_column}':", 
                options=unique_values,
                default=unique_values 
            )

        # Thực hiện lọc dựa trên lựa chọn
        filtered_df = data[data[selected_column].isin(selected_values)]

        # Hiển thị kết quả lọc
        st.write(f"Tìm thấy **{len(filtered_df)}** dòng phù hợp với bộ lọc.")
        st.dataframe(filtered_df, use_container_width=True)

        # ---------------------------------------------------------
        # BƯỚC 3: XUẤT EXCEL CHO DỮ LIỆU ĐÃ LỌC
        # ---------------------------------------------------------
        if not filtered_df.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data_Da_Loc')
            
            st.download_button(
                label="📥 Tải kết quả lọc về Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"ket_qua_loc_{selected_column}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Đã xảy ra lỗi khi đọc file: {e}")
