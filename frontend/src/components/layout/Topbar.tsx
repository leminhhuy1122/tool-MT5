import React, { useEffect, useState } from 'react';
import {
  Bell,
  Clock,
  Maximize,
  Menu,
  Minimize,
  Monitor,
  RefreshCw,
  Zap,
} from 'lucide-react';
import type { BotStatus, MT5Status } from '../../types';

interface TopbarProps {
  symbol: string;
  mt5Status: MT5Status;
  botStatus: BotStatus;
  onRefresh: () => void;
  isRefreshing: boolean;
  onOpenMobileMenu: () => void;
  density: 'normal' | 'compact';
  onToggleDensity: () => void;
  pollIntervalSec: number;
  onChangePollInterval: (sec: number) => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  symbol,
  mt5Status,
  botStatus,
  onRefresh,
  isRefreshing,
  onOpenMobileMenu,
  density,
  onToggleDensity,
  pollIntervalSec,
  onChangePollInterval,
}) => {
  const [currentTime, setCurrentTime] = useState<string>('');
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  useEffect(() => {
    const update = () => {
      const now = new Date();
      const hours = String(now.getUTCHours()).padStart(2, '0');
      const mins = String(now.getUTCMinutes()).padStart(2, '0');
      const secs = String(now.getUTCSeconds()).padStart(2, '0');
      setCurrentTime(`${hours}:${mins}:${secs} UTC`);
    };
    update();
    const timer = setInterval(update, 1000);

    const onFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);

    return () => {
      clearInterval(timer);
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []);

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Mobile menu trigger */}
        <button
          className="btn-icon"
          onClick={onOpenMobileMenu}
          style={{ display: 'none' }}
          id="mobile-menu-btn"
          title="Mở menu"
        >
          <Menu size={18} />
        </button>

        {/* Current Symbol */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
            }}
          >
            <Zap size={14} className="text-gold" />
            <span className="font-mono font-bold text-sm text-primary">{symbol}</span>
            <span className="text-xs text-muted">GOLD SPOT</span>
          </div>

          {/* Bot Status */}
          <div className={`status-pill ${botStatus.toLowerCase()}`}>
            <span className={`live-dot ${botStatus === 'RUNNING' ? 'pulse' : ''}`} />
            BOT {botStatus}
          </div>

          {/* MT5 Status */}
          <div className={`status-pill ${mt5Status.toLowerCase()}`}>
            <span className={`live-dot ${mt5Status === 'CONNECTED' ? 'pulse' : ''}`} />
            MT5 {mt5Status}
          </div>

          {/* Live Desktop Client Indicator */}
          <div
            className="status-pill demo"
            style={{
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              color: '#60A5FA',
              borderColor: 'rgba(59, 130, 246, 0.3)',
            }}
          >
            <Monitor size={12} />
            DESKTOP CLIENT
          </div>
        </div>
      </div>

      <div className="topbar-right">
        {/* Polling Interval Selector */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            backgroundColor: 'var(--bg-card-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '2px 4px',
          }}
          title="Tần suất tự động làm mới từ backend"
        >
          <span className="text-xs text-muted" style={{ padding: '0 4px' }}>Feed:</span>
          {[
            { label: '5s', val: 5 },
            { label: '10s', val: 10 },
            { label: '30s', val: 30 },
          ].map((item) => (
            <button
              key={item.val}
              onClick={() => onChangePollInterval(item.val)}
              style={{
                background: pollIntervalSec === item.val ? 'var(--color-accent-gold)' : 'transparent',
                color: pollIntervalSec === item.val ? '#0B0F19' : 'var(--text-secondary)',
                border: 'none',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.12s ease',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* UTC Clock */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            padding: '5px 10px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--bg-card-subtle)',
            border: '1px solid var(--border-subtle)',
            whiteSpace: 'nowrap',
          }}
        >
          <Clock size={13} className="text-gold" />
          <span>{currentTime || 'Loading...'}</span>
        </div>

        {/* Refresh button */}
        <button
          className="btn-icon"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Làm mới dữ liệu từ backend MT5 ngay lập tức"
        >
          <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
        </button>

        {/* Density Mode Toggle */}
        <button
          className={`btn-icon ${density === 'compact' ? 'active' : ''}`}
          onClick={onToggleDensity}
          title={density === 'compact' ? 'Chuyển sang chế độ xem chuẩn (Normal)' : 'Chuyển sang chế độ xem thu gọn (Compact Mode)'}
        >
          <span style={{ fontSize: '11px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
            {density === 'compact' ? 'COMP' : 'NORM'}
          </span>
        </button>

        {/* Fullscreen Toggle */}
        <button
          className={`btn-icon ${isFullscreen ? 'active' : ''}`}
          onClick={handleToggleFullscreen}
          title={isFullscreen ? 'Thoát toàn màn hình' : 'Mở toàn màn hình (Trading Desk)'}
        >
          {isFullscreen ? <Minimize size={14} /> : <Maximize size={14} />}
        </button>

        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button className="btn-icon" title="Thông báo hệ thống">
            <Bell size={15} />
            <span
              style={{
                position: 'absolute',
                top: '6px',
                right: '6px',
                width: '6px',
                height: '6px',
                backgroundColor: 'var(--color-accent-gold)',
                borderRadius: '50%',
              }}
            />
          </button>
        </div>
      </div>
    </header>
  );
};
