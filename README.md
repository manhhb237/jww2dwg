# Bộ Chuyển Đổi Hàng Loạt JWW sang DWG

Ứng dụng chuyển đổi hàng loạt bản vẽ từ định dạng Jw_cad (.jww) sang định dạng AutoCAD (.dwg) chất lượng cao, giữ nguyên font chữ tiếng Nhật, màu sắc, layer và các loại nét vẽ mà không bị lỗi.

## Các tính năng chính
- **Chuyển đổi hàng loạt (Batch conversion)**: Quét và convert toàn bộ danh sách file trong thư mục nguồn cùng lúc.
- **Chuyển đổi thông minh**: 
  - **Giữ nguyên Font chữ**: Áp dụng mã hóa Shift-JIS và chuyển đổi Unicode dạng `\U+XXXX` giúp AutoCAD hiển thị đúng font (MS Gothic, MS Mincho...) mà không lỗi ô vuông (`[]` hay `?`).
  - **Giữ nguyên kiểu nét**: Tự định nghĩa đầy đủ linetype pattern (nét đứt, nét chấm gạch...) tương thích AutoCAD thay vì chỉ map tên nét.
- **ODA File Converter**: Tự động nhận diện ODA File Converter trên hệ thống để xuất file DWG (AutoCAD 2018, 2013, 2010...). Nếu không có ODA Converter, chương trình vẫn hỗ trợ xuất sang DXF.
- **Giao diện đa ngôn ngữ**: Switch chuyển đổi nhanh chóng giữa **Tiếng Việt** và **Tiếng Nhật (日本語)**.
- **Giao diện hiện đại**: Thiết kế tối giản, Dark Mode cao cấp, hiển thị tiến trình chuyển đổi real-time.

## Cấu trúc thư mục dự án
```
jww2dwg/
├── app.py              # File chạy chính của giao diện Tkinter
├── converter.py        # Module xử lý chuyển đổi logic (ezjww + ezdxf.addons.odafc)
├── requirements.txt    # Danh sách thư viện phụ thuộc
├── run.bat             # File chạy nhanh ứng dụng
└── README.md           # Hướng dẫn sử dụng này
```

## Hướng dẫn cài đặt và sử dụng

### 1. Yêu cầu hệ thống
- Hệ điều hành: Windows
- Đã cài đặt **Python 3.13** (đã cấu hình sẵn thông qua môi trường ảo `venv`).
- Đã cài đặt **ODA File Converter** (đã được cài tự động thông qua `winget` trong quá trình cài đặt).

### 2. Cách chạy ứng dụng
1. Nhấp đúp vào file `run.bat` trong thư mục này.
2. Giao diện chương trình sẽ xuất hiện.

### 3. Các bước chuyển đổi
1. Chọn thư mục chứa các file `.jww` nguồn ở dòng **Thư mục JWW nguồn**.
2. Chọn thư mục lưu file `.dwg` đầu ra ở dòng **Thư mục DWG đầu ra**.
3. Chọn phiên bản DWG mong muốn (Mặc định: `R2018`).
4. Nhấp nút **▶ Bắt đầu chuyển đổi** (hoặc **▶ 変換実行** nếu chuyển sang giao diện Tiếng Nhật).
5. Sau khi hoàn thành, file `.dwg` sẽ nằm trong thư mục đầu ra.
