# LDPlayer Lite Manager

Ứng dụng Windows bằng Python 3.12 để quản lý nhiều instance LDPlayer và áp dụng cấu hình nhẹ theo cách có thể kiểm tra, sao lưu và khôi phục. Bản hiện tại hoàn thành phạm vi MVP trong `noidung.md`.

## Chức năng

- Tự động tìm `ldconsole.exe` và `adb.exe`, hoặc cho phép chọn thủ công.
- Liệt kê, tạo, nhân bản, đổi tên, khởi động, dừng, khởi động lại và xóa instance.
- Áp dụng profile CPU, RAM, độ phân giải, DPI và FPS cho một hoặc nhiều instance.
- Bật/tắt animation Android qua ADB khi instance đang chạy.
- Áp dụng FPS, tắt âm thanh và memory optimization bằng `globalsetting` của LDMultiPlayer.
- Tự dừng rồi khởi động lại instance đang chạy để cấu hình thực sự có hiệu lực.
- Giữ ưu tiên tiến trình bình thường trong lúc boot, sau đó hạ xuống theo profile để giảm tranh chấp CPU.
- Khởi động nhiều instance theo thứ tự, có thời gian nghỉ để tránh tăng tải đột ngột.
- Chạy ADB shell, kết nối thiết bị và chụp màn hình PNG.
- Kiểm tra DNS, route, ping IP và ping tên miền trực tiếp từ Android của LDPlayer.
- Quét ứng dụng Android theo từng instance, phân biệt package người dùng và hệ thống.
- Vô hiệu hóa bằng `pm disable-user`, bật lại hoặc khôi phục trạng thái từ backup; không tự động uninstall.
- Khóa thao tác với System UI, Settings, launcher, Google Play Services và Android provider thiết yếu.
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

Nút **Khởi động** và **Khởi động tất cả** trong Manager dùng luồng khởi động tối ưu: áp cài đặt đa phiên, đợi từng Android sẵn sàng, tắt animation rồi mới hạ độ ưu tiên tiến trình. Nút **Tối ưu** tự khởi động lại các instance đang chạy vì LDPlayer chỉ nhận đầy đủ CPU, RAM, độ phân giải và cài đặt đa phiên sau khi restart.

`globalsetting` khác nhau giữa các đời LDPlayer. Nếu bản đang dùng không hỗ trợ, Manager vẫn áp dụng CPU/RAM/độ phân giải và hiển thị cảnh báo để bạn bật FPS, tắt audio và Memory optimization trong cửa sổ LDMultiPlayer.

Nếu mạng trong LDPlayer bị chậm hoặc khựng, dùng profile **Ổn định mạng**. Profile này dùng 2 CPU, 1536 MB RAM, 30 FPS, ưu tiên tiến trình bình thường và tắt memory optimization để tránh Android bị thiếu thời gian CPU hoặc phải thu hồi bộ nhớ liên tục. Trong trang **ADB**, chọn thiết bị rồi bấm **Kiểm tra mạng** để xem ping theo IP và tên miền; ping IP tốt nhưng ping tên miền lỗi thường chỉ ra vấn đề DNS.

## Tắt ứng dụng không cần thiết

Mở instance, vào trang **Ứng dụng**, chọn thiết bị ADB rồi bấm **Quét package**. Danh sách mặc định chỉ hiện ứng dụng người dùng; bật **Hiện package hệ thống** khi cần kiểm tra sâu hơn. Chọn package và bấm **Vô hiệu hóa đã chọn**. Manager lưu trạng thái trước thay đổi tại `%APPDATA%\LDPlayerLiteManager\backups\packages`, vì vậy có thể bật lại hoặc dùng **Khôi phục từ backup**.

Nếu chỉ cần chạy một ứng dụng, nhập package vào ô **Chỉ cần chạy** rồi bấm **Phân tích ứng dụng mục tiêu**. Manager giữ ứng dụng mục tiêu cùng Play Store, Google Play Services, GSF, WebView/Chrome, Download Manager, launcher và các thành phần Android thiết yếu; các package tùy chọn phù hợp để tắt thử sẽ được đánh dấu sẵn nhưng chưa bị thay đổi cho tới khi bạn bấm **Vô hiệu hóa đã chọn**.

Nhãn **Nên xem xét** được suy ra từ tên package liên quan đến quảng cáo, analytics, app store, đề xuất, browser hoặc live wallpaper. Đây chỉ là gợi ý để kiểm tra, Manager không tự chọn và không tự tắt package nào.

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
