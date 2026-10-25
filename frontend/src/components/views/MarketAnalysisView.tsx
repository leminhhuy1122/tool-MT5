import React from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  Compass,
  Layers,
  Minus,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { MarketOverviewData, MarketTrend } from '../../types';

interface MarketAnalysisViewProps {
  data: MarketOverviewData;
}

export const MarketAnalysisView: React.FC<MarketAnalysisViewProps> = ({ data }) => {
  const isPositive = data.change24h >= 0;

  const renderTrendBox = (label: string, timeframe: string, trend: MarketTrend, desc: string) => {
    const isBull = trend === 'BULLISH';
    const isBear = trend === 'BEARISH';
    const colorClass = isBull ? 'text-buy' : isBear ? 'text-sell' : 'text-wait';
    const bgClass = isBull ? 'var(--color-buy-bg)' : isBear ? 'var(--color-sell-bg)' : 'var(--color-wait-bg)';
    const borderClass = isBull ? 'var(--color-buy-border)' : isBear ? 'var(--color-sell-border)' : 'var(--color-wait-border)';
    const icon = isBull ? <ArrowUpRight size={18} /> : isBear ? <ArrowDownRight size={18} /> : <Minus size={18} />;

    return (
      <div
        className="card"
        style={{
          borderLeft: `3px solid ${isBull ? 'var(--color-buy)' : isBear ? 'var(--color-sell)' : 'var(--color-wait)'}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div>
            <span className="font-mono font-bold text-base text-primary">{timeframe}</span>
            <span className="text-xs text-muted" style={{ marginLeft: '8px' }}>{label}</span>
          </div>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 10px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11px',
              fontWeight: 800,
              backgroundColor: bgClass,
              borderColor: borderClass,
              borderWidth: '1px',
              borderStyle: 'solid',
            }}
            className={colorClass}
          >
            {icon}
            {trend}
          </span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {desc}
        </p>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Stat Bar */}
      <div
        className="card"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
          gap: '16px',
        }}
      >
        <div>
          <div className="text-xs text-secondary font-semibold uppercase">Giá XAUUSD Thực Tế (MT5)</div>
          <div className="font-mono font-extrabold text-2xl text-gold" style={{ marginTop: '4px' }}>
            ${data.price.toFixed(2)}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              marginTop: '4px',
              fontSize: '12px',
              fontWeight: 600,
            }}
            className={isPositive ? 'text-buy' : 'text-sell'}
          >
            {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span>
              {isPositive ? '+' : ''}${data.change24h.toFixed(2)} ({isPositive ? '+' : ''}
              {data.change24hPct.toFixed(2)}%)
            </span>
          </div>
        </div>

        <div>
          <div className="text-xs text-secondary font-semibold uppercase">Biên Độ Phiên 24h</div>
          <div className="font-mono text-sm text-primary" style={{ marginTop: '6px' }}>
            High: <span className="text-buy font-bold">${data.high24h.toFixed(2)}</span>
          </div>
          <div className="font-mono text-sm text-primary" style={{ marginTop: '2px' }}>
            Low: <span className="text-sell font-bold">${data.low24h.toFixed(2)}</span>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
            Biên độ: ${(data.high24h - data.low24h).toFixed(2)} giá
          </div>
        </div>

        <div>
          <div className="text-xs text-secondary font-semibold uppercase">Biến Động & Thanh Khoản</div>
          <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '6px' }}>
            {data.volatility}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
            Spread Broker: <strong className="font-mono text-gold">{data.spread.toFixed(2)}</strong> giá
          </div>
        </div>

        <div>
          <div className="text-xs text-secondary font-semibold uppercase">Thời Gian Cập Nhật</div>
          <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '6px' }}>
            {data.lastUpdate}
          </div>
          <div className="text-xs text-buy" style={{ marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span className="live-dot pulse" /> Dữ liệu trực tiếp từ MetaTrader 5
          </div>
        </div>
      </div>

      {/* Multi-Timeframe Trend Grid */}
      <div>
        <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Compass size={18} className="text-gold" />
          Phân Tích Cấu Trúc Xu Hướng Đa Khung Thời Gian
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', gap: '14px' }}>
          {renderTrendBox('Macro Trend', 'H4 (240 Phút)', data.h4Trend, 'Xác lập xu hướng vĩ mô dài hạn, định hướng chiến lược tổng thể toàn phiên giao dịch.')}
          {renderTrendBox('Core Trend', 'H1 (60 Phút)', data.h1Trend, 'Xác định phe mua/bán đang làm chủ vùng thanh khoản chính trong ngày.')}
          {renderTrendBox('Intermediate', 'M15 (15 Phút)', data.m15Trend, 'Định vị vùng cân bằng, các đợt hồi quy (pullback) và cấu trúc sóng con.')}
          {renderTrendBox('Entry Confirm', 'M5 (5 Phút)', data.m5Confirmation, 'Khung thời gian thực thi: Nhận diện mô hình đảo chiều, Breakout và kích hoạt tín hiệu.')}
        </div>
      </div>

      {/* Structure & S/R Zones Banner */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Layers size={16} className="text-gold" /> Chi Tiết Cấu Trúc & Vùng Hỗ Trợ / Kháng Cự (S/R)
          </span>
          <span className="text-xs text-gold font-mono">Tự Động Tính Toán &bull; Không Look-Ahead</span>
        </div>
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            fontSize: '13px',
            lineHeight: 1.6,
          }}
        >
          <div style={{ marginBottom: '8px' }}>
            <strong className="text-primary">Trạng thái cấu trúc: </strong>
            <span className="font-mono text-gold font-bold">{data.structure}</span>
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Thuật toán tự động tìm đỉnh đáy cục bộ (Swing Highs / Lows), vẽ các vùng cung cầu (Supply/Demand Zones),
            và theo dõi sự thay đổi cấu trúc thị trường (BOS - Break of Structure / CHoCH - Change of Character)
            để đảm bảo tín hiệu vào lệnh luôn đồng thuận theo xu hướng tổ chức.
          </div>
        </div>
      </div>
    </div>
  );
};
