import React from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  Compass,
  Layers,
  Minus,
  Sliders,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import type { MarketOverviewData, MarketTrend, StatusCardData } from '../../types';

interface MarketTickerHeroProps {
  statusCards: StatusCardData;
  marketOverview: MarketOverviewData;
  onRefresh?: () => void;
}

const TrendPill: React.FC<{ label: string; trend: MarketTrend }> = ({ label, trend }) => {
  const isBull = trend === 'BULLISH';
  const isBear = trend === 'BEARISH';

  let color = '#F59E0B';
  let bg = 'rgba(245, 158, 11, 0.12)';
  let border = 'rgba(245, 158, 11, 0.3)';
  let icon = <Minus size={11} />;

  if (isBull) {
    color = '#10B981';
    bg = 'rgba(16, 185, 129, 0.12)';
    border = 'rgba(16, 185, 129, 0.3)';
    icon = <ArrowUpRight size={11} />;
  } else if (isBear) {
    color = '#EF4444';
    bg = 'rgba(239, 68, 68, 0.12)';
    border = 'rgba(239, 68, 68, 0.3)';
    icon = <ArrowDownRight size={11} />;
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '5px 10px',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: bg,
        border: `1px solid ${border}`,
        fontSize: '11px',
        fontWeight: 600,
      }}
    >
      <span style={{ color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '10px' }}>{label}</span>
      <span style={{ color, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
        {icon}
        {trend}
      </span>
    </div>
  );
};

export const MarketTickerHero: React.FC<MarketTickerHeroProps> = ({ statusCards, marketOverview }) => {
  const currentPrice = statusCards.currentPrice || marketOverview.price;
  const isPositive = marketOverview.change24h >= 0;
  const spread = statusCards.spread || marketOverview.spread;
  const askPrice = currentPrice + spread;

  // Tính vị trí % của giá trong biên độ 24h
  const rangeSpan = Math.max(0.1, marketOverview.high24h - marketOverview.low24h);
  const pricePct = Math.min(100, Math.max(0, ((currentPrice - marketOverview.low24h) / rangeSpan) * 100));

  return (
    <div
      className="card"
      id="market-ticker-hero-card"
      style={{
        marginBottom: '12px',
        background: 'linear-gradient(135deg, rgba(21, 28, 43, 0.98) 0%, rgba(14, 20, 34, 0.95) 100%)',
        border: '1px solid rgba(245, 158, 11, 0.35)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
        position: 'relative',
        overflow: 'hidden',
        padding: '16px 22px',
        borderRadius: '14px',
      }}
    >
      {/* Decorative top gold gradient accent line */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '3px',
          background: 'linear-gradient(90deg, #F59E0B 0%, #10B981 50%, #F59E0B 100%)',
        }}
      />

      {/* BỐ CỤC 3 PHẦN CÂN ĐỐI: CÁNH TRÁI (THÔNG SỐ) - Ở GIỮA (VÒNG TRÒN NỔI BẬT BO TRÒN) - CÁNH PHẢI (MA TRẬN XU HƯỚNG) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        {/* CÁNH TRÁI: THỐNG KÊ KHỚP LỆNH & BIÊN ĐỘ 24H */}
        <div style={{ flex: '1 1 260px', minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                color: '#F59E0B',
                padding: '2px 8px',
                borderRadius: 'var(--radius-sm)',
                fontWeight: 800,
                fontSize: '11px',
                letterSpacing: '0.05em',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Zap size={13} /> {marketOverview.symbol || 'XAUUSD'}
            </span>
            <span className="text-xs text-secondary font-bold uppercase tracking-wider">THÔNG SỐ KHỚP LỆNH</span>
          </div>

          {/* Cặp Bid / Ask */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div
              style={{
                padding: '7px 10px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ fontSize: '10px' }}>Giá Mua (Bid)</div>
              <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '2px' }}>
                ${currentPrice.toFixed(2)}
              </div>
            </div>

            <div
              style={{
                padding: '7px 10px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ fontSize: '10px' }}>Giá Bán (Ask)</div>
              <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '2px' }}>
                ${askPrice.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Spread Vàng */}
          <div
            style={{
              padding: '6px 10px',
              backgroundColor: 'rgba(245, 158, 11, 0.08)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <Sliders size={12} className="text-gold" /> Spread Thực Chiến:
            </span>
            <span className="font-mono font-extrabold text-xs text-gold">
              {spread.toFixed(2)} giá <span style={{ fontSize: '10px', fontWeight: 500, color: 'var(--text-muted)' }}>(~{(spread * 10).toFixed(0)} pips)</span>
            </span>
          </div>

          {/* Thanh Biên Độ 24h High - Low */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px', fontSize: '10px' }}>
              <span style={{ color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Activity size={11} className="text-gold" /> Biên Độ 24h
              </span>
              <span className="font-mono text-xs text-primary font-semibold">Vị trí: {pricePct.toFixed(0)}%</span>
            </div>
            <div
              style={{
                position: 'relative',
                height: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
                borderRadius: 'var(--radius-full)',
                overflow: 'hidden',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: `${pricePct}%`,
                  background: 'linear-gradient(90deg, #EF4444 0%, #F59E0B 50%, #10B981 100%)',
                  borderRadius: 'var(--radius-full)',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '3px', fontSize: '9px' }}>
              <span className="font-mono text-sell">Low: ${marketOverview.low24h.toFixed(2)}</span>
              <span className="font-mono text-buy">High: ${marketOverview.high24h.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* TRỌNG TÂM Ở GIỮA: VÒNG TRÒN BO TRÒN TRANG TRÍ ĐẸP & NỔI BẬT (ORBITAL GOLD DIAL) */}
        <div
          style={{
            flex: '0 0 auto',
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '6px',
          }}
        >
          <div
            style={{
              width: '190px',
              height: '190px',
              borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(245, 158, 11, 0.25) 0%, rgba(15, 23, 42, 0.92) 68%, rgba(11, 15, 25, 0.98) 100%)',
              border: '2.5px solid #F59E0B',
              boxShadow: '0 0 35px rgba(245, 158, 11, 0.45), inset 0 0 25px rgba(245, 158, 11, 0.2)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              textAlign: 'center',
              padding: '14px',
            }}
          >
            {/* Vòng radar nét đứt bên trong */}
            <div
              style={{
                position: 'absolute',
                top: '7px',
                left: '7px',
                right: '7px',
                bottom: '7px',
                borderRadius: '50%',
                border: '1px dashed rgba(245, 158, 11, 0.4)',
                pointerEvents: 'none',
              }}
            />

            {/* Tag nhỏ ở đỉnh vòng tròn */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '9px',
                fontWeight: 800,
                color: '#10B981',
                padding: '2px 7px',
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                borderRadius: 'var(--radius-full)',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                marginBottom: '4px',
              }}
            >
              <span className="live-dot pulse" style={{ width: '5px', height: '5px' }} />
              MT5 LIVE TICK
            </div>

            {/* GIÁ VÀNG LỚN Ở CHÍNH GIỮA VÒNG TRÒN */}
            <div
              className="font-mono font-extrabold text-gold"
              style={{
                fontSize: '30px',
                lineHeight: 1.1,
                letterSpacing: '-0.02em',
                textShadow: '0 0 25px rgba(245, 158, 11, 0.6), 0 2px 4px rgba(0, 0, 0, 0.95)',
                fontWeight: 900,
                marginTop: '2px',
                marginBottom: '5px',
              }}
            >
              ${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>

            {/* Thẻ biến động 24h ở đáy vòng tròn */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                fontWeight: 800,
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: isPositive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                border: `1px solid ${isPositive ? 'rgba(16, 185, 129, 0.45)' : 'rgba(239, 68, 68, 0.45)'}`,
                boxShadow: isPositive ? '0 0 10px rgba(16, 185, 129, 0.25)' : '0 0 10px rgba(239, 68, 68, 0.25)',
              }}
              className={isPositive ? 'text-buy' : 'text-sell'}
            >
              {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              <span>
                {isPositive ? '+' : ''}${marketOverview.change24h.toFixed(2)} ({isPositive ? '+' : ''}
                {marketOverview.change24hPct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        {/* CÁNH PHẢI: MA TRẬN XU HƯỚNG ĐA KHUNG & CẤU TRÚC SMC */}
        <div style={{ flex: '1 1 260px', minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Layers size={13} className="text-gold" /> MA TRẬN XU HƯỚNG 4 KHUNG
            </span>
            <span className="text-xs text-gold font-mono" style={{ fontSize: '10px' }}>
              ATR: {marketOverview.volatility}
            </span>
          </div>

          {/* Lưới 4 Khung thời gian H4, H1, M15, M5 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
            <TrendPill label="H4 Macro" trend={marketOverview.h4Trend} />
            <TrendPill label="H1 Core" trend={marketOverview.h1Trend} />
            <TrendPill label="M15 Intra" trend={marketOverview.m15Trend} />
            <TrendPill label="M5 Entry" trend={marketOverview.m5Confirmation} />
          </div>

          {/* Tóm tắt Cấu trúc Thị trường SMC */}
          <div
            style={{
              padding: '8px 10px',
              backgroundColor: 'var(--bg-card-subtle)',
              borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--color-accent-gold)',
            }}
          >
            <div className="text-xs text-secondary font-semibold" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px' }}>
              <Compass size={11} className="text-gold" /> Cấu trúc nến M5:
            </div>
            <div className="font-mono text-xs text-primary font-bold" style={{ marginTop: '2px', fontSize: '11px' }}>
              {marketOverview.structure}
            </div>
          </div>
        </div>
      </div>

      {/* DẢI FOOTER NHỎ Ở ĐÁY SECTION GIÁ VÀNG */}
      <div
        style={{
          marginTop: '12px',
          paddingTop: '8px',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '10px',
          color: 'var(--text-muted)',
          flexWrap: 'wrap',
          gap: '6px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>
            Bot Engine: <strong className="text-gold">v1.0-M5 SMC+OB</strong>
          </span>
          <span>•</span>
          <span>
            Quy tắc: <strong>Lãi 5 giá dời BE, Lãi 8 giá Trailing Stop</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Clock size={11} /> Cập nhật tick: <span className="font-mono text-secondary">{marketOverview.lastUpdate}</span>
        </div>
      </div>
    </div>
  );
};
