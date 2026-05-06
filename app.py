import streamlit as st
import pandas as pd
import io

# Thiết lập tiêu đề cho trang web
st.title("🔄 Công cụ chuyển đổi JSON sang Excel")
st.write("Tải file JSON của bạn lên, hệ thống sẽ đọc, lọc dữ liệu và xuất ra file Excel.")

# Tạo nút upload file
uploaded_file = st.file_uploader("Chọn file JSON", type=["json"])

if uploaded_file is not None:
    try:
        # 1. Đọc dữ liệu JSON vào Pandas DataFrame
        df = pd.read_json(uploaded_file)
        
        st.subheader("Dữ liệu gốc:")
        st.dataframe(df)

        # 2. LỌC DỮ LIỆU (Tùy chỉnh tại đây)
        # Ví dụ 1: Chỉ lấy các cột cụ thể
        # df_filtered = df[['Tên', 'Tuổi', 'Email']]
        
        # Ví dụ 2: Lọc các dòng có điều kiện (ví dụ: Tuổi > 18)
        # df_filtered = df[df['Tuổi'] > 18]
        
        # Tạm thời mặc định giữ nguyên toàn bộ dữ liệu:
        df_filtered = df 

        st.subheader("Dữ liệu sau khi lọc (Sẵn sàng xuất Excel):")
        st.dataframe(df_filtered)

        # 3. Tạo file Excel trong bộ nhớ ảo (không lưu xuống ổ cứng server)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_filtered.to_excel(writer, index=False, sheet_name='Data')

        # 4. Tạo nút tải xuống
        st.download_button(
            label="📥 Tải xuống file Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="Du_lieu_da_chuyen_doi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Có lỗi xảy ra khi xử lý file: {e}\nVui lòng kiểm tra lại cấu trúc file JSON của bạn.")
