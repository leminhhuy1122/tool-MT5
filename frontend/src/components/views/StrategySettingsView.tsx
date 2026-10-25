import React from 'react';
import {
  CheckCircle2,
  Cpu,
  Layers,
  ShieldAlert,
  Sliders,
  Target,
  Zap,
} from 'lucide-react';

export const StrategySettingsView: React.FC = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Banner */}
      <div
        className="card"
        style={{
          borderLeft: '4px solid var(--color-accent-gold)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={20} className="text-gold" />
            Chiến Lược Giao Dịch: v1.0-M5 Multi-Timeframe Institutional
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Hệ thống xác định cấu trúc đa khung thời gian H4 - H1 - M15 - M5 kết hợp mô hình học máy Random Forest.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className="status-pill connected">PHIÊN BẢN CHÍNH THỨC</span>
          <span className="status-pill demo">ML FILTER: BẬT</span>
        </div>
      </div>

      {/* Strategy Rules Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: '16px' }}>
        {/* Rule 1: Entry */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Zap size={16} className="text-gold" /> 1. Điểm Vào Lệnh (Entry Zone)
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>±1 GIÁ</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Điểm vào lệnh hợp lệ nằm trong phạm vi dung sai <strong className="text-gold font-mono">±1 giá</strong> so với giá kích hoạt tín hiệu.
            Nếu giá thị trường vượt quá dung sai ±1 giá trước khi khớp, lệnh sẽ tự động hủy kích hoạt để bảo toàn R:R.
          </div>
        </div>

        {/* Rule 2: Breakeven */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <CheckCircle2 size={16} className="text-buy" /> 2. Quản Lý Hòa Vốn (Breakeven)
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>LÃI +5 GIÁ</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Ngay khi giá vàng chạy theo đúng hướng và đạt lợi nhuận <strong className="text-buy font-mono">+5 giá ($5.00/oz)</strong>:
            <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
              <li>Tự động dời Stop Loss về chính xác điểm hòa vốn (Entry Price).</li>
              <li>Loại bỏ 100% rủi ro mất vốn cho vị thế đang mở.</li>
            </ul>
          </div>
        </div>

        {/* Rule 3: Partial TP1 & Trailing */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Target size={16} className="text-gold" /> 3. Chốt 1 Phần & Khóa Lãi TP1
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>LÃI +10 GIÁ</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Khi giá đạt lợi nhuận mục tiêu <strong className="text-gold font-mono">+10 giá (TP1)</strong>:
            <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
              <li>Tự động chốt <strong className="text-primary font-mono">50% khối lượng</strong> vị thế.</li>
              <li>Dời Stop Loss dương lên mức có lãi để bảo vệ thành quả.</li>
              <li>Giữ 50% khối lượng còn lại thả trôi nuôi lợi nhuận tối đa đến <strong className="text-buy font-mono">TP2</strong>.</li>
            </ul>
          </div>
        </div>

        {/* Rule 4: Stop Loss Protection */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <ShieldAlert size={16} className="text-sell" /> 4. Cắt Lỗ An Toàn (Stop Loss)
            </span>
            <span className="status-pill disconnected" style={{ fontSize: '10px' }}>SWING LOW/HIGH</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Stop Loss được tính toán khách quan dựa trên cấu trúc sóng nến:
            <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
              <li>Lệnh BUY: SL đặt dưới Swing Low gần nhất cộng thêm bộ đệm spread.</li>
              <li>Lệnh SELL: SL đặt trên Swing High gần nhất cộng thêm bộ đệm spread.</li>
              <li>Không bao giờ di dời SL xa hơn điểm rủi ro ban đầu.</li>
            </ul>
          </div>
        </div>

        {/* Rule 5: ML Quality Classifier */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Cpu size={16} className="text-gold" /> 5. Bộ Lọc Trí Tuệ Nhân Tạo (ML Filter)
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>RANDOM FOREST</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Mô hình Machine Learning trích xuất 14 đặc trưng kỹ thuật:
            <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
              <li>Confidence &ge; 60%: Cộng thêm điểm hợp lưu chất lượng cao.</li>
              <li>Confidence &lt; 35%: Tự động lọc bỏ tín hiệu vì rủi ro đảo chiều cao.</li>
              <li>Kiểm định Time Series Split không rò rỉ dữ liệu tương lai.</li>
            </ul>
          </div>
        </div>

        {/* Rule 6: Multi-Timeframe Alignment */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Layers size={16} className="text-gold" /> 6. Hợp Lưu Đa Khung Thời Gian
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>H4 &bull; H1 &bull; M15 &bull; M5</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Nguyên tắc phân tích đa tầng:
            <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
              <li><strong>H4:</strong> Xu hướng vĩ mô (Macro Trend).</li>
              <li><strong>H1:</strong> Xu hướng chủ đạo xác định phe mua/bán chiếm ưu thế.</li>
              <li><strong>M15:</strong> Cấu trúc sóng trung hạn và các vùng S/R quan trọng.</li>
              <li><strong>M5:</strong> Khung thời gian thực thi tìm điểm vào tối ưu.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
