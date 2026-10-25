# CẨM NANG ĐỌC BIỂU ĐỒ SMART MONEY CONCEPTS (SMC) & QUY TẮC RA LỆNH VÀNG (XAUUSD)
> **Tài liệu chuẩn hóa dành cho Hệ thống Bot VietKey Gold AI & Nhà giao dịch**  
> *Phiên bản: v2.5 — Bản quyền thuộc về VietKey Institutional Trading Terminal*

---

## 1. TỔNG QUAN PHƯƠNG PHÁP SMART MONEY CONCEPTS (SMC)

Khác với các phương pháp kỹ thuật bán lẻ thông thường (chỉ dựa vào đường chỉ báo trễ như RSI, Stoch hay các mô hình nến đơn lẻ), **Smart Money Concepts (SMC)** tập trung giải mã **hành vi của dòng tiền lớn (Institutional Banks, Quỹ phòng hộ Hedge Funds)** trên thị trường tài chính, đặc biệt là thị trường Vàng (XAUUSD).

Dòng tiền lớn không vào lệnh cùng một lúc mà luôn thực hiện 3 bước:
1. **Thu gom thanh khoản (Liquidity Collection):** Đẩy giá quét các mức đỉnh/đáy quen thuộc để kích hoạt Stop Loss của phe bán lẻ.
2. **Bứt phá mất cân bằng (Displacement / FVG):** Bơm vốn cực lớn tạo ra các nến thân dài, để lại các vùng mất cân bằng cung cầu (Fair Value Gap).
3. **Quay lại đón thêm vị thế (Mitigation / Retest):** Giá hồi nhẹ về vùng giá chiết khấu (Discount) hoặc giá đắt (Premium) tại các khối Order Block để khớp nốt vị thế tồn đọng trước khi bung mạnh theo xu hướng chính.

---

## 2. FAIR VALUE GAP (FVG) — KHOẢNG TRỐNG GIÁ MẤT CÂN BẰNG

### 2.1. Bản chất của FVG
**Fair Value Gap (FVG)** là vùng mất cân bằng thanh khoản xảy ra khi một bên (Mua hoặc Bán) chiếm ưu thế áp đảo hoàn toàn, khiến giá chạy quá nhanh trong 1 nến mà không có sự đối ứng của phe còn lại. Thị trường luôn có xu hướng tự nhiên quay lại lấp đầy (mitigate) khoảng trống này để thiết lập lại sự cân bằng.

### 2.2. Nhận diện hình học trên biểu đồ (Mô hình 3 nến)
* **Bullish FVG (Khoảng trống tăng giá):**
  - **Nến 1:** Nến chuẩn bị.
  - **Nến 2:** Nến xanh tăng cực mạnh (thân dài vượt trội).
  - **Nến 3:** Nến tiếp diễn tăng.
  - **Vùng FVG:** Khoảng cách giữa **Đỉnh (High) của Nến 1** và **Đáy (Low) của Nến 3** mà thân nến không chạm tới nhau.
  - **Ý nghĩa:** Vùng giá này chỉ có người Mua, thiếu vắng người Bán. Khi giá giảm về vùng này, các lệnh Chờ Mua (Buy Limit) của tổ chức sẽ kích hoạt lực đẩy giá bật tăng trở lại.

* **Bearish FVG (Khoảng trống giảm giá):**
  - **Nến 1:** Nến chuẩn bị.
  - **Nến 2:** Nến đỏ giảm cực mạnh (thân dài vượt trội).
  - **Nến 3:** Nến tiếp diễn giảm.
  - **Vùng FVG:** Khoảng cách giữa **Đáy (Low) của Nến 1** và **Đỉnh (High) của Nến 3**.
  - **Ý nghĩa:** Vùng giá chỉ có người Bán. Khi giá hồi lên vùng này, áp lực bán mạnh mẽ sẽ đẩy giá giảm tiếp.

### 2.3. Mức C.E (Consequent Encroachment — 50% FVG)
* Mức giá chính giữa (50% của FVG) được gọi là **Consequent Encroachment (C.E)**.
* Đây là mức phản ứng nhạy bén nhất. Khi nến hồi chạm đúng 50% FVG và rút râu nến là tín hiệu xác nhận vào lệnh có xác suất thắng cao nhất.

---

## 3. ORDER BLOCK (OB) — KHỐI LỆNH TỔ CHỨC

### 3.1. Khái niệm Order Block
Order Block là cây nến ngược hướng cuối cùng trước một đợt sóng bứt phá cực mạnh (Displacement) phá vỡ cấu trúc đỉnh/đáy (BOS). Đây là nơi các “ông lớn” đặt khối lượng lệnh tích lũy khổng lồ.

* **Bullish Order Block (+OB):** Cây nến GIẢM cuối cùng trước khi giá bung tăng mạnh mẽ tạo ra FVG và phá vỡ cấu trúc đỉnh cũ.
* **Bearish Order Block (-OB):** Cây nến TĂNG cuối cùng trước khi giá xả bán mạnh mẽ tạo ra FVG và đâm thủng cấu trúc đáy cũ.

### 3.2. Tiêu chí xác thực một OB chất lượng cao (High Probability OB)
1. **Có Displacement rõ ràng:** Nến ngay sau OB phải là nến thân dài dứt khoát.
2. **Kèm theo FVG:** Đợt sóng sau OB phải để lại một khoảng trống FVG chưa bị lấp.
3. **Phá vỡ cấu trúc (BOS):** Sóng bứt phá phải phá vỡ Swing High hoặc Swing Low quan trọng.
4. **Chưa bị Mitigate (Unmitigated):** Giá chưa từng quay lại chạm vào vùng thân/râu của OB này kể từ lúc hình thành.

---

## 4. LIQUIDITY SWEEPS (SĂN THANH KHOẢN / BẪY GIÁ)

### 4.1. Thanh khoản nằm ở đâu trên thị trường Vàng?
* **Buy-Side Liquidity (BSL):** Tập trung ở phía TRÊN các đỉnh Swing High, đỉnh ngày hôm trước (Previous Day High - PDH), hoặc vùng hai đỉnh bằng nhau (Equal Highs - EQH). Nơi này chứa hàng nghìn lệnh Stop Loss của phe SELL và lệnh Buy Stop đột phá.
* **Sell-Side Liquidity (SSL):** Tập trung ở phía DƯỚI các đáy Swing Low, đáy ngày hôm trước (Previous Day Low - PDL), hoặc vùng hai đáy bằng nhau (Equal Lows - EQL). Nơi này chứa hàng nghìn lệnh Stop Loss của phe BUY và lệnh Sell Stop phá đáy.

### 4.2. Cơ chế Săn Thanh Khoản (Stop Hunt / Fakeout)
1. Nhà cái đẩy giá vượt qua đỉnh cũ (BSL) hoặc thủng đáy cũ (SSL).
2. Trader bán lẻ tưởng rằng giá "breakout" nên nhảy vào đu theo, đồng thời các lệnh Stop Loss bị kích hoạt (tạo ra thanh khoản khớp lệnh dồi dào cho tổ chức).
3. Ngay lập tức nến đóng cửa quay đầu giật lại vào bên trong biên giới hạn, để lại một **râu nến rất dài (Long Wick Rejection)**.
4. Đây là thời điểm vàng để hệ thống bot vào lệnh đảo chiều ngược lại bẫy giá!

---

## 5. DISCOUNT VS PREMIUM — VÙNG GIÁ CÂN BẰNG (EQUILIBRIUM 50%)

Không bao giờ mua ở mức giá đắt và không bao giờ bán ở mức giá rẻ!
* **Equilibrium (Mức 50%):** Trung điểm của biên độ dao động sóng (Swing Range).
* **Discount Zone (< 50%):** Vùng chiết khấu — Chỉ tìm kiếm setup **BUY** khi giá nằm trong vùng này kết hợp Bullish FVG hoặc Bullish OB.
* **Premium Zone (> 50%):** Vùng giá đắt đỏ — Chỉ tìm kiếm setup **SELL** khi giá nằm trong vùng này kết hợp Bearish FVG hoặc Bearish OB.

---

## 6. CẤU TRÚC RA LỆNH CHUẨN TỐI ƯU TỶ LỆ ĂN TP CAO

Theo yêu cầu chuẩn hóa thực chiến cho cặp Vàng (XAUUSD):

### 6.1. Quy chuẩn Stop Loss (SL): 10 giá hoặc hơn 1 xíu (10.0 – 12.0 giá)
* **Khoảng cách SL chuẩn:** Từ **10.0 đến 12.0 giá** (tương đương 100 – 120 pips).
* **Vị trí đặt SL:**
  - Lệnh BUY: Đặt dưới đáy râu nến quét thanh khoản (SSL) hoặc dưới đáy của Bullish Order Block từ 0.5 – 1.0 giá, với độ rộng tối thiểu 10.0 giá và tối đa 12.0 giá.
  - Lệnh SELL: Đặt trên đỉnh râu nến quét thanh khoản (BSL) hoặc trên đỉnh của Bearish Order Block từ 0.5 – 1.0 giá, với độ rộng tối thiểu 10.0 giá và tối đa 12.0 giá.
* **Lợi ích:** Khoảng cách 10-12 giá đủ rộng để tránh các đợt quét râu ngẫu nhiên (spread/slippage của sàn), đồng thời đủ hẹp để bảo vệ tài khoản nếu xu hướng bị phá vỡ hoàn toàn.

### 6.2. Cấu trúc Mục tiêu Chốt Lời (Take Profit):
1. **Take Profit 1 (TP1): 10.0 – 12.0 giá (Tỷ lệ 1:1 — Tỷ lệ ăn TP > 75%)**
   - Đặt tại khoảng cách đúng bằng độ rộng Stop Loss (+10.0 đến +12.0 giá).
   - Với các setup SMC (bật từ FVG hoặc rút râu sau Liquidity Sweep), một nhịp nảy 10 giá diễn ra rất nhanh và xác suất đạt cực kỳ cao.
   - **Hành động khi chạm TP1:** Chốt lời 50% – 70% khối lượng lệnh.

2. **Cơ chế Tự Động Kéo SL Về Hòa Vốn (Breakeven - BE):**
   - Ngay thời khắc giá thị trường chạm mức TP1, hệ thống bot tự động dời mức `Stop Loss` về đúng mức `Entry Price` (hoặc dời SL dương +1 giá).
   - **Kết quả:** Lệnh đã chốt lời được một khoản lợi nhuận lớn ở TP1, và phần còn lại có rủi ro bằng 0 (Zero Risk). Dù thị trường có đảo chiều giật ngược lại thì tài khoản vẫn thắng 100%!

3. **Take Profit 2 (TP2): 20.0 – 24.0 giá (Tỷ lệ 1:2 — Gồng lãi theo xu hướng)**
   - Dành cho phần khối lượng còn lại thả trôi theo con sóng chính của khung H1/H4.
   - Đạt được mức biên độ lợi nhuận tối đa mà không chịu bất kỳ áp lực tâm lý nào.

---

## 7. BẢNG TỔNG HỢP SETUP ĐƯỢC LẬP TRÌNH TRONG BOT

| Setup Type | Tên Setup | Điều kiện kích hoạt | Vị trí Entry | SL | TP1 / TP2 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SMC_LIQUIDITY_SWEEP` | Săn thanh khoản (Stop Hunt) | Râu nến quét qua Swing High/Low, đóng nến rút râu trở lại | Giá Close của nến quét | 10.0 - 12.0 giá (sau râu quét) | TP1: 10-12 giá (Ăn cao)<br>TP2: 20-24 giá |
| `SMC_FVG_RETEST` | Hồi quy khoảng trống giá | Giá hồi về chạm mép hoặc 50% C.E của FVG chưa lấp | Vùng 50% C.E của FVG | 10.0 - 12.0 giá (sau mép FVG) | TP1: 10-12 giá (Kéo BE)<br>TP2: 20-24 giá |
| `SMC_ORDER_BLOCK` | Retest khối lệnh tổ chức | Giá thoái lui về chạm vùng Bullish/Bearish Order Block | Vùng 50% Mean của OB | 10.0 - 12.0 giá (sau đáy/đỉnh OB) | TP1: 10-12 giá (Kéo BE)<br>TP2: 20-24 giá |
| `BOS_RETEST` | Phá vỡ & Hồi test cấu trúc | Giá tạo BOS theo xu hướng H4 và hồi về kiểm tra lại đỉnh/đáy | Đỉnh/đáy vừa phá vỡ | 10.0 - 12.0 giá | TP1: 10-12 giá<br>TP2: 20-24 giá |
| `EMA_BOUNCE` | Tiếp diễn đà xu hướng EMA | Giá hồi chạm vùng hỗ trợ động EMA21/EMA50 trên khung H1 | Vùng EMA | 10.0 - 12.0 giá | TP1: 10-12 giá<br>TP2: 20-24 giá |
