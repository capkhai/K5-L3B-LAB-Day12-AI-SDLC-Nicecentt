# Kiểm chứng sprite Chợ Nổi

- Đã mở bản live bằng Edge headless, nạp atlas `song-nuoc.png`, vẽ cảnh gather, kiểm tra tám hình Sổ tay có pixel hiển thị và gọi hàm vẽ cá đang bơi cho cả bốn loài. Các sự kiện sinh cá, mọc lại và chuyển buổi không tạo chú thích. Bộ unittest chạy lại đạt 144/144.

- Kiểm tra atlas thủy quái bằng Edge headless qua máy chủ live trên localhost. Canvas vẽ cảnh gather với hai thủy quái, tải ảnh rộng 1254 px. Client bỏ chú thích `fish_spawned`, `node_regrown`, `gather_end`, `phase_start` và vẫn có cảnh báo dòng nước lũ.
- Sau thay đổi chuyển động và chú thích, bộ unittest chạy bằng Python cục bộ trên Windows đạt 144/144.

- Suite `python -m unittest discover -s tests` đạt 32/32. Trên Windows, dùng `sys.executable` thay alias `python3` trong tiến trình test khi gọi headless.
- Khởi động `LiveServer` ở cả `gather` và `quan`, tải HTML và atlas qua HTTP, kiểm tra MIME `image/png`, ảnh RGBA và 12 vùng sprite có cả pixel trong suốt lẫn pixel đục.
- Ảnh được kiểm tra trực quan qua bản xem trước ImageGen. Chưa kiểm tra canvas bằng trình duyệt.
- Animation bơi dùng `ut-sen-swim.png`. Đã tải PNG qua HTTP ở chế độ `gather` và kiểm tra sáu vùng RGBA có nền trong suốt. Suite chạy lại đạt 32/32.
