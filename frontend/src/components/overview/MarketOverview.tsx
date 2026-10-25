import React from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  Layers,
  Minus,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { MarketOverviewData, MarketTrend } from '../../types';

interface MarketOverviewProps {
  data: MarketOverviewData;
}

const TrendBadge: React.FC<{ trend: MarketTrend; label: string }> = ({ trend, label }) => {
  const isBull = trend === 'BULLISH';
  const isBear = trend === 'BEARISH';

  let colorClass = 'text-wait';
  let bgClass = 'var(--color-wait-bg)';
  let borderClass = 'var(--color-wait-border)';
  let icon = <Minus size={14} />;

  if (isBull) {
    colorClass = 'text-buy';
    bgClass = 'var(--color-buy-bg)';
    borderClass = 'var(--color-buy-border)';
    icon = <ArrowUpRight size={14} />;
  } else if (isBear) {
    colorClass = 'text-sell';
    bgClass = 'var(--color-sell-bg)';
    borderClass = 'var(--color-sell-border)';
    icon = <ArrowDownRight size={14} />;
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 14px',
        backgroundColor: 'var(--bg-card-subtle)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
      }}
    >
      <span className="font-semibold text-xs text-secondary">{label}</span>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 8px',
          borderRadius: 'var(--radius-sm)',
          fontSize: '11px',
          fontWeight: 700,
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
  );
};

export const MarketOverview: React.FC<MarketOverviewProps> = ({ data }) => {
  const isPositive = data.change24h >= 0;

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <Layers size={16} className="text-gold" /> Phân Tích Cấu Trúc Thị Trường XAUUSD
        </span>
        <span className="text-xs text-secondary font-mono">{data.lastUpdate}</span>
      </div>

      {/* Primary Price & 24h Stats */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          padding: '16px',
          backgroundColor: 'var(--bg-card-subtle)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-subtle)',
          marginBottom: '20px',
        }}
      >
        <div>
          <div className="text-xs text-secondary">Giá Thị Trường (Bid)</div>
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
            <span className="text-muted font-normal text-xs">24h</span>
          </div>
        </div>

        <div>
          <div className="text-xs text-secondary">Biên Độ 24 Giờ</div>
          <div className="font-mono text-sm text-primary" style={{ marginTop: '6px' }}>
            High: <span className="text-buy font-bold">${data.high24h.toFixed(2)}</span>
          </div>
          <div className="font-mono text-sm text-primary" style={{ marginTop: '2px' }}>
            Low: <span className="text-sell font-bold">${data.low24h.toFixed(2)}</span>
          </div>
        </div>

        <div>
          <div className="text-xs text-secondary">Độ Biến Động ATR(14)</div>
          <div className="font-mono font-semibold text-sm text-primary" style={{ marginTop: '6px' }}>
            {data.volatility}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
            Spread hiện tại: <strong className="font-mono text-gold">{data.spread.toFixed(2)}</strong> giá
          </div>
        </div>
      </div>

      {/* Multi-Timeframe Matrix */}
      <div style={{ marginBottom: '16px' }}>
        <div className="text-xs text-secondary font-semibold text-uppercase" style={{ marginBottom: '8px' }}>
          Ma Trận Xu Hướng Đa Khung Thời Gian (Multi-Timeframe Trend)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' }}>
          <TrendBadge label="H4 Macro Trend" trend={data.h4Trend} />
          <TrendBadge label="H1 Core Trend" trend={data.h1Trend} />
          <TrendBadge label="M15 Intermediate" trend={data.m15Trend} />
          <TrendBadge label="M5 Entry Confirm" trend={data.m5Confirmation} />
        </div>
      </div>

      {/* Market Structure Summary */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'var(--bg-card-subtle)',
          borderRadius: 'var(--radius-sm)',
          borderLeft: '3px solid var(--color-accent-gold)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <span className="text-xs text-secondary font-semibold">Cấu trúc thị trường hiện tại: </span>
          <span className="font-mono text-sm text-primary font-medium">{data.structure}</span>
        </div>
        <span className="text-xs text-gold font-mono">Rule-based No Look-ahead</span>
      </div>
    </div>
  );
};
