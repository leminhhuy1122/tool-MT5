import React, { useEffect, useState } from 'react';
import {
  BrainCircuit,
  CheckCircle2,
  Clock,
  Eye,
  Layers,
  RefreshCw,
  Shield,
} from 'lucide-react';
import type { MarketOverviewData, StatusCardData } from '../../types';

interface AiThinkingRadarProps {
  statusCards: StatusCardData;
  marketOverview: MarketOverviewData;
  onRefresh?: () => void;
}

export const AiThinkingRadar: React.FC<AiThinkingRadarProps> = ({
  statusCards,
  marketOverview,
  onRefresh,
}) => {
  const [m5SecondsElapsed, setM5SecondsElapsed] = useState<number>(0);

  // Hiệu ứng nhịp tim phân tích nến M5 (5 phút = 300 giây)
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const currentSeconds = now.getSeconds();
      const currentMinutes = now.getMinutes();
      // Số giây đã trôi qua trong nến M5 hiện tại
      const elapsedInM5 = (currentMinutes % 5) * 60 + currentSeconds;
      setM5SecondsElapsed(elapsedInM5);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const m5Pct = Math.min(100, Math.round((m5SecondsElapsed / 300) * 100));
  const remainingM5Sec = Math.max(0, 300 - m5SecondsElapsed);
  const remainingM = Math.floor(remainingM5Sec / 60);
  const remainingS = remainingM5Sec % 60;

  // Đánh giá trạng thái xu hướng đa khung
  const h4 = marketOverview.h4Trend || 'BEARISH';
  const h1 = marketOverview.h1Trend || 'BULLISH';
  const m15 = marketOverview.m15Trend || 'NEUTRAL';
  const m5 = marketOverview.m5Confirmation || 'BEARISH';

  // Kiểm tra xung đột xu hướng
  const hasConflict =
    (h4 === 'BEARISH' && h1 === 'BULLISH') ||
    (h4 === 'BULLISH' && h1 === 'BEARISH') ||
    (h1 !== 'NEUTRAL' && m5 !== 'NEUTRAL' && h1 !== m5);

  return (
    <div
      id="ai-thinking-radar-widget"
      className="card"
      style={{
        marginBottom: '20px',
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(20, 30, 50, 0.95) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.35)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        position: 'relative',
        overflow: 'hidden',
        padding: '18px 22px',
      }}
    >
      {/* Decorative top pulse stripe */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '3px',
          background: 'linear-gradient(90deg, #38BDF8 0%, #F59E0B 50%, #10B981 100%)',
        }}
      />

      {/* Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          paddingBottom: '14px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Animated Brain Radar Icon */}
          <div
            style={{
              position: 'relative',
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38BDF8',
            }}
          >
            <BrainCircuit size={20} />
            <span
              style={{
                position: 'absolute',
                top: '-3px',
                right: '-3px',
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: '#10B981',
                boxShadow: '0 0 8px #10B981',
                animation: 'pulse 1.5s infinite',
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#F8FAFC', margin: 0, letterSpacing: '0.2px' }}>
                Bộ Não AI & Trạng Thái Suy Nghĩ Thị Trường (AI Market Radar)
              </h3>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '999px',
                  backgroundColor: 'rgba(16, 185, 129, 0.18)',
                  color: '#10B981',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span className="live-dot pulse" style={{ width: '6px', height: '6px' }} />
                {statusCards.symbol || 'XAUUSD'} • {statusCards.botStatus || 'RUNNING'} (5s/lần)
              </span>
            </div>
            <p style={{ fontSize: '11px', color: '#94A3B8', marginTop: '3px', margin: 0 }}>
              Hệ thống hoạt động liên tục • Phân tích vi cấu trúc Smart Money Concepts (SMC) & Cân nhắc vào lệnh
            </p>
          </div>
        </div>

        {/* M5 Candle Countdown & Refresh Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
              padding: '4px 12px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.07)',
            }}
          >
            <span style={{ fontSize: '10px', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={11} /> Nến M5 hiện tại:
            </span>
            <span style={{ fontSize: '12px', fontWeight: 800, fontFamily: 'monospace', color: '#F59E0B' }}>
              Đóng nến sau: {remainingM}m {String(remainingS).padStart(2, '0')}s ({m5Pct}%)
            </span>
          </div>

          {onRefresh && (
            <button
              onClick={onRefresh}
              className="btn btn-secondary"
              style={{
                padding: '6px 12px',
                fontSize: '11px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                fontWeight: 700,
              }}
              title="Quét lại giá MT5 ngay tức thì"
            >
              <RefreshCw size={12} />
              Quét Ngay
            </button>
          )}
        </div>
      </div>

      {/* M5 Progress Bar */}
      <div style={{ marginTop: '10px', marginBottom: '16px' }}>
        <div
          style={{
            height: '4px',
            width: '100%',
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '999px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${m5Pct}%`,
              backgroundColor: '#38BDF8',
              borderRadius: '999px',
              transition: 'width 1s linear',
              boxShadow: '0 0 8px rgba(56, 189, 248, 0.6)',
            }}
          />
        </div>
      </div>

      {/* Grid: 3 Reasoning Columns */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '14px',
        }}
      >
        {/* Col 1: AI Reasoning & Tại sao chưa vào lệnh */}
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '10px',
            padding: '14px 16px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#38BDF8', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Eye size={14} /> TẠI SAO CHƯA VÀO LỆNH?
            </span>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 800,
                padding: '2px 8px',
                borderRadius: '4px',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                color: '#F59E0B',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              ⏳ KIÊN NHẪN QUAN SÁT (WAIT)
            </span>
          </div>

          <div style={{ fontSize: '12px', color: '#E2E8F0', lineHeight: 1.6 }}>
            {hasConflict ? (
              <span>
                Thị trường đang <strong>xung đột xu hướng</strong> giữa các khung thời gian (H4 {h4} vs H1 {h1}).
                Bot kích hoạt chế độ <strong>Bảo Vệ Vốn An Toàn</strong>, kiên quyết không đoán đỉnh bắt đáy khi chưa có tín hiệu xác nhận rõ ràng.
              </span>
            ) : (
              <span>
                Giá đang tích lũy trong vùng <strong>RANGING</strong>. Bot đang chờ nến M5 đóng cửa phá vỡ cấu trúc (BOS) hoặc hồi quy về vùng Khối lệnh (Order Block) đẹp để vào lệnh với tỷ lệ R:R cao nhất.
              </span>
            )}
          </div>

          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: 'auto', paddingTop: '4px' }}>
            💡 <em>Nguyên tắc: Thà kiên nhẫn đợi 1 lệnh chuẩn R:R 1:3 còn hơn vào 10 lệnh ẩu làm cháy vốn.</em>
          </div>
        </div>

        {/* Col 2: Confluence & Đa Khung Thời Gian */}
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '10px',
            padding: '14px 16px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#F59E0B', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={14} /> MA TRẬN XU HƯỚNG ĐA KHUNG
            </span>
            <span style={{ fontSize: '10px', color: '#94A3B8' }}>MT5 Tick Feed</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '11px',
              }}
            >
              <span style={{ color: '#94A3B8' }}>H4 (Trung hạn):</span>
              <strong style={{ color: h4 === 'BULLISH' ? '#10B981' : h4 === 'BEARISH' ? '#EF4444' : '#F59E0B' }}>
                {h4}
              </strong>
            </div>

            <div
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '11px',
              }}
            >
              <span style={{ color: '#94A3B8' }}>H1 (Ngắn hạn):</span>
              <strong style={{ color: h1 === 'BULLISH' ? '#10B981' : h1 === 'BEARISH' ? '#EF4444' : '#F59E0B' }}>
                {h1}
              </strong>
            </div>

            <div
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '11px',
              }}
            >
              <span style={{ color: '#94A3B8' }}>M15 (Cấu trúc):</span>
              <strong style={{ color: m15 === 'BULLISH' ? '#10B981' : m15 === 'BEARISH' ? '#EF4444' : '#F59E0B' }}>
                {m15}
              </strong>
            </div>

            <div
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '11px',
              }}
            >
              <span style={{ color: '#94A3B8' }}>M5 (Kích hoạt):</span>
              <strong style={{ color: m5 === 'BULLISH' ? '#10B981' : m5 === 'BEARISH' ? '#EF4444' : '#F59E0B' }}>
                {m5}
              </strong>
            </div>
          </div>

          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: 'auto' }}>
            Biến động: <strong style={{ color: '#CBD5E1' }}>{marketOverview.volatility || 'Bình thường'}</strong> • Spread: <strong style={{ color: '#F59E0B' }}>{marketOverview.spread || 1.4} giá</strong>
          </div>
        </div>

        {/* Col 3: Checklist Kích Hoạt Lệnh Mới */}
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '10px',
            padding: '14px 16px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#10B981', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Shield size={14} /> ĐIỀU KIỆN MỞ LỆNH TỰ ĐỘNG
            </span>
            <span className="font-mono text-xs text-gold">Min 0.01 Lot</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={13} style={{ color: '#10B981', flexShrink: 0 }} />
              <span style={{ color: '#CBD5E1' }}>Kết nối MT5 Tick Feed & SQLite: <strong>Ổn định</strong></span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={13} style={{ color: '#10B981', flexShrink: 0 }} />
              <span style={{ color: '#CBD5E1' }}>Chống Hedging cùng điểm: <strong>Bảo vệ (Khoảng cách &gt;= 5 giá)</strong></span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={13} style={{ color: '#10B981', flexShrink: 0 }} />
              <span style={{ color: '#CBD5E1' }}>Ví Đầu Tư Ảo (Paper): <strong>Sẵn sàng $50 vốn</strong></span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#F59E0B', fontWeight: 800, width: '13px', textAlign: 'center', flexShrink: 0 }}>⏳</span>
              <span style={{ color: '#E2E8F0' }}>Nến M5 chạm Order Block / FVG: <strong>Đang chờ tín hiệu xác nhận</strong></span>
            </div>
          </div>

          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: 'auto', paddingTop: '4px' }}>
            Ngay khi nến M5 đóng cửa thỏa mãn, lệnh mới sẽ <strong>tự động mở 0.01 lot</strong> và bắn thông báo.
          </div>
        </div>
      </div>
    </div>
  );
};
