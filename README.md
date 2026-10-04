# LDPlayer Lite Manager

Ứng dụng Windows bằng Python 3.12 để quản lý nhiều instance LDPlayer và áp dụng cấu hình nhẹ theo cách có thể kiểm tra, sao lưu và khôi phục. Bản hiện tại hoàn thành phạm vi MVP trong `noidung.md`.

## Chức năng

- Tự động tìm `ldconsole.exe` và `adb.exe`, hoặc cho phép chọn thủ công.
- Liệt kê, tạo, nhân bản, đổi tên, khởi động, dừng, khởi động lại và xóa instance.
- Áp dụng profile CPU, RAM, độ phân giải, DPI và FPS cho một hoặc nhiều instance.
- Bật/tắt animation Android qua ADB khi instance đang chạy.
- Khởi động nhiều instance theo thứ tự, có thời gian nghỉ để tránh tăng tải đột ngột.
- Chạy ADB shell, kết nối thiết bị và chụp màn hình PNG.
- Tự động sao lưu file cấu hình instance trước khi tối ưu nếu file đó có trong installation LDPlayer.
- Khôi phục backup trong GUI hoặc CLI; instance phải được dừng trước khi khôi phục.
- Có GUI PySide6 và CLI `ldlite`.

Ứng dụng không sửa binary, kernel hay phân vùng hệ thống Android. Thao tác xóa instance luôn yêu cầu xác nhận trong GUI.

## Cài đặt

Mở PowerShell tại thư mục dự án:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Nếu LDPlayer không được phát hiện, vào **Cài đặt** và chọn trực tiếp `ldconsole.exe` cùng `adb.exe`.

## CLI

```powershell
python main.py detect
python main.py list
python main.py start 0
python main.py stop 0
python main.py restart 0
python main.py optimize 0 --profile Lite
python main.py optimize-all --profile "Ultra Lite"
python main.py start-all --delay 10
python main.py stop-all
python main.py restore "%APPDATA%\LDPlayerLiteManager\backups\instance_0\<timestamp>"
python main.py adb 127.0.0.1:5555 getprop
python main.py screenshot 127.0.0.1:5555
```

Có thể thêm `--console C:\...\ldconsole.exe` hoặc `--adb C:\...\adb.exe` trước subcommand khi cần chỉ định đường dẫn.

## Profile

Các profile nằm trong `config/profiles.json`. Profile Lite mặc định dùng 1 CPU, 512 MB RAM, 540×960, DPI 160 và 20 FPS. Hãy tăng RAM nếu ứng dụng Android bị đóng do thiếu bộ nhớ.

Cấu hình cá nhân, log, ảnh và backup được lưu tại:

```text
%APPDATA%\LDPlayerLiteManager
```

## Automation tùy chọn

Các helper chụp ảnh, tap, swipe, OpenCV template matching và OCR đã có sẵn. Cài dependency khi cần:

```powershell
python -m pip install -r requirements-automation.txt
```

OCR còn yêu cầu Tesseract được cài trên Windows và có trong `PATH`.

## Kiểm thử và build EXE

```powershell
python -m unittest discover -s tests -v
.\build.ps1
```

File build xuất hiện tại `dist\LDPlayerLiteManager.exe`.

## Lưu ý tương thích

LDPlayer thay đổi cú pháp và vị trí file cấu hình giữa các phiên bản. Các thao tác instance dùng giao diện dòng lệnh chính thức của `ldconsole`. Nên thử profile trên một instance đã dừng trước khi áp dụng cho toàn bộ 12 instance.
