import React from 'react';
import {
  Activity,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Radio,
  Settings,
  Wallet,
} from 'lucide-react';
import type { BotStatus, MenuId } from '../../types';

interface SidebarProps {
  currentMenu: MenuId;
  onSelectMenu: (menuId: MenuId) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  botStatus: BotStatus;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const PRIMARY_NAV_ITEMS: { id: MenuId; label: string; icon: React.ReactNode; badge?: string; desc: string }[] = [
  {
    id: 'overview',
    label: 'Tổng Quan',
    icon: <Activity size={18} />,
    badge: 'Live',
    desc: 'Giá vàng MT5 & Cấu trúc thị trường',
  },
  {
    id: 'signals',
    label: 'Tín Hiệu & Lệnh',
    icon: <Radio size={18} />,
    badge: 'Admin',
    desc: 'Nhật ký lệnh & Bắn lại Telegram',
  },
  {
    id: 'paper-wallet',
    label: 'Ví Đầu Tư Ảo',
    icon: <Wallet size={18} />,
    badge: '0.01 Lot',
    desc: 'Giả lập nạp vốn $50 & tự động khớp lệnh',
  },
  {
    id: 'news',
    label: 'Tin Tức & Dự Báo AI',
    icon: <Calendar size={18} />,
    badge: 'AI Bias',
    desc: 'Lịch kinh tế & Dự đoán xu hướng',
  },
  {
    id: 'system',
    label: 'Hệ Thống & Tìm Lỗi',
    icon: <Settings size={18} />,
    badge: 'Monitor',
    desc: 'Giám sát bot, xem log & bắt lỗi',
  },
];

export const Sidebar: React.FC<SidebarProps> = ({
  currentMenu,
  onSelectMenu,
  collapsed,
  onToggleCollapse,
  botStatus,
  mobileOpen,
  onCloseMobile,
}) => {
  // Normalize legacy menu IDs to one of the primary tabs
  const activePrimaryId: MenuId =
    currentMenu === 'overview'
      ? 'overview'
      : currentMenu === 'signals' || currentMenu === 'live-signals' || currentMenu === 'signal-history'
      ? 'signals'
      : currentMenu === 'news' || currentMenu === 'economic-calendar'
      ? 'news'
      : currentMenu === 'paper-wallet'
      ? 'paper-wallet'
      : 'system';

  return (
    <>
      {mobileOpen && <div className="mobile-overlay" onClick={onCloseMobile} />}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
        {/* Header Logo */}
        <div className="sidebar-header">
          <div className="brand-wrapper">
            <div className="brand-logo-icon">🏆</div>
            {!collapsed && (
              <div className="brand-text-block">
                <span className="brand-title">VIETKEY GOLD AI</span>
                <span className="brand-subtitle">Trading Terminal</span>
              </div>
            )}
          </div>
          <button
            className="btn-icon"
            onClick={onToggleCollapse}
            title={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
            style={{ width: '28px', height: '28px' }}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Bot Status Banner in Sidebar */}
        {!collapsed && (
          <div style={{ padding: '12px 14px 6px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <span className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="text-gold font-bold">🤖</span> Bot Engine:
              </span>
              <span className={`status-pill ${botStatus.toLowerCase()}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                <span className={`live-dot ${botStatus === 'RUNNING' ? 'pulse' : ''}`} />
                {botStatus}
              </span>
            </div>
          </div>
        )}

        {/* Primary 4 Navigation Tabs */}
        <nav className="nav-section" style={{ padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {PRIMARY_NAV_ITEMS.map((item) => {
            const isActive = activePrimaryId === item.id;
            return (
              <button
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  onSelectMenu(item.id);
                  onCloseMobile();
                }}
                title={collapsed ? `${item.label} — ${item.desc}` : undefined}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: collapsed ? '10px' : '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  position: 'relative',
                  border: isActive ? '1px solid var(--color-accent-gold)' : '1px solid transparent',
                  backgroundColor: isActive ? 'rgba(245, 158, 11, 0.12)' : 'transparent',
                  transition: 'all 0.15s ease',
                }}
              >
                <span className="nav-item-icon" style={{ color: isActive ? 'var(--color-accent-gold)' : 'inherit' }}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className="nav-item-label" style={{ fontWeight: isActive ? 700 : 500, fontSize: '13px' }}>
                        {item.label}
                      </span>
                      {item.badge && (
                        <span
                          className="nav-badge"
                          style={{
                            fontSize: '9px',
                            padding: '1px 6px',
                            backgroundColor: isActive ? 'var(--color-accent-gold)' : 'var(--bg-card-subtle)',
                            color: isActive ? '#0B0F19' : 'var(--text-secondary)',
                            fontWeight: 700,
                            borderRadius: '4px',
                          }}
                        >
                          {item.badge}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.desc}
                    </span>
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer Info */}
        {!collapsed && (
          <div className="sidebar-footer" style={{ marginTop: 'auto', borderTop: '1px solid var(--border-subtle)', padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
              <span>📡 Kênh: <strong>@dbgtradingfx</strong></span>
              <span className="font-mono text-gold font-bold">v0.8.0</span>
            </div>
          </div>
        )}
      </aside>
    </>
  );
};
