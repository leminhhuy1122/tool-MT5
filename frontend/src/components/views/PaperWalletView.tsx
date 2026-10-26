import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  DollarSign,
  History,
  Layers,
  Loader2,
  Play,
  Power,
  RefreshCw,
  RotateCcw,
  Sliders,
  TrendingUp,
  Wallet,
  X,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import type {
  PaperEquitySnapshot,
  PaperPositionItem,
  PaperTradeHistoryItem,
  PaperWalletData,
} from '../../types';

export const PaperWalletView: React.FC = () => {
  const [wallet, setWallet] = useState<PaperWalletData | null>(null);
  const [positions, setPositions] = useState<PaperPositionItem[]>([]);
  const [history, setHistory] = useState<PaperTradeHistoryItem[]>([]);
  const [equityCurve, setEquityCurve] = useState<PaperEquitySnapshot[]>([]);

  // Loading states riêng biệt cho từng hành động
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isSettingUp, setIsSettingUp] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [isTogglingAuto, setIsTogglingAuto] = useState<boolean>(false);
  const [closingPositionId, setClosingPositionId] = useState<string | null>(null);

  // Active bottom tab: 'positions' | 'history'
  const [activeTab, setActiveTab] = useState<'positions' | 'history'>('positions');

  // Toast feedback
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Form input states
  const [depositAmount, setDepositAmount] = useState<string>('50');
  const [lotSize, setLotSize] = useState<string>('0.01');
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadWalletData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    try {
      const [ovRes, posRes, histRes, curveRes] = await Promise.allSettled([
        api.getPaperWalletOverview(),
        api.getPaperPositions(),
        api.getPaperHistory(50),
        api.getPaperEquityCurve(100),
      ]);

      if (ovRes.status === 'fulfilled') {
        setWallet(ovRes.value.wallet);
        // Đồng bộ form amount ban đầu nếu chưa nhập
        if (!depositAmount || depositAmount === '50') {
          setDepositAmount(String(ovRes.value.wallet.initial_balance || 50));
        }
        setLotSize(String(ovRes.value.wallet.default_lot || 0.01));
      }
      if (posRes.status === 'fulfilled') setPositions(posRes.value);
      if (histRes.status === 'fulfilled') setHistory(histRes.value);
      if (curveRes.status === 'fulfilled') setEquityCurve(curveRes.value);
    } catch (err) {
      console.error('Lỗi nạp dữ liệu Ví ảo:', err);
    } finally {
      setIsLoading(false);
      if (isManualRefresh) setIsRefreshing(false);
    }
  }, [depositAmount]);

  // Polling tự động mỗi 3 giây để cập nhật giá Live và PnL thả nổi
  useEffect(() => {
    loadWalletData(false);
    const interval = setInterval(() => {
      loadWalletData(false);
    }, 3000);
    return () => clearInterval(interval);
  }, [loadWalletData]);

  // 1. Nạp vốn / Thay đổi cấu hình
  const handleSetupWallet = async () => {
    const amount = parseFloat(depositAmount);
    const lot = parseFloat(lotSize);
    if (isNaN(amount) || amount < 10) {
      showToast('Vui lòng nhập số vốn tối thiểu từ $10.00 trở lên!', 'error');
      return;
    }
    setIsSettingUp(true);
    try {
      const res = await api.setupPaperWallet({ initial_balance: amount, default_lot: lot });
      if (res.ok) {
        showToast(res.message, 'success');
        setWallet(res.wallet);
        await loadWalletData(false);
      }
    } catch (err: any) {
      showToast(err.message || 'Lỗi thiết lập ví', 'error');
    } finally {
      setIsSettingUp(false);
    }
  };

  // 2. Reset ví về mốc ban đầu
  const handleResetWallet = async () => {
    setIsResetting(true);
    try {
      const amount = parseFloat(depositAmount) || 50.0;
      const res = await api.resetPaperWallet(amount);
      if (res.ok) {
        showToast(res.message, 'success');
        setWallet(res.wallet);
        setShowResetConfirm(false);
        await loadWalletData(false);
      }
    } catch (err: any) {
      showToast(err.message || 'Lỗi reset ví', 'error');
    } finally {
      setIsResetting(false);
    }
  };

  // 3. Bật/Tắt tự động khớp lệnh bot
  const handleToggleAuto = async () => {
    setIsTogglingAuto(true);
    try {
      const res = await api.togglePaperAutoTrading();
      if (res.ok) {
        showToast(res.message, 'success');
        if (wallet) {
          setWallet({ ...wallet, is_auto_trading: res.is_auto_trading });
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Lỗi bật tắt auto trading', 'error');
    } finally {
      setIsTogglingAuto(false);
    }
  };

  // 4. Đóng lệnh thủ công
  const handleClosePosition = async (positionId: string) => {
    setClosingPositionId(positionId);
    try {
      const res = await api.closePaperPosition(positionId);
      if (res.ok) {
        showToast(res.message, 'success');
        await loadWalletData(false);
      }
    } catch (err: any) {
      showToast(err.message || 'Lỗi đóng lệnh', 'error');
    } finally {
      setClosingPositionId(null);
    }
  };

  // Helper chọn số tiền nhanh
  const setQuickAmount = (amt: number) => {
    setDepositAmount(String(amt));
  };

  const addAmount = (delta: number) => {
    const cur = parseFloat(depositAmount) || 50;
    setDepositAmount(String(Math.max(10, cur + delta)));
  };

  // Render SVG biểu đồ vốn Equity Curve
  const renderEquityCurveSvg = () => {
    if (!equityCurve || equityCurve.length < 2) {
      return (
        <div style={{ height: '170px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '13px', gap: '8px' }}>
          <TrendingUp size={24} color="#64748b" style={{ opacity: 0.5 }} />
          <span>Chưa có đủ điểm dữ liệu. Biểu đồ sẽ tự vẽ khi có lệnh đóng hoàn tất.</span>
        </div>
      );
    }

    const values = equityCurve.map((d) => d.equity);
    const minVal = Math.min(...values) * 0.98;
    const maxVal = Math.max(...values) * 1.02;
    const range = maxVal - minVal || 1;

    const width = 640;
    const height = 170;
    const paddingX = 24;
    const paddingY = 24;

    const points = equityCurve
      .map((d, idx) => {
        const x = paddingX + (idx / (equityCurve.length - 1)) * (width - paddingX * 2);
        const y = height - paddingY - ((d.equity - minVal) / range) * (height - paddingY * 2);
        return `${x},${y}`;
      })
      .join(' ');

    const isGrowing = values[values.length - 1] >= values[0];
    const strokeColor = isGrowing ? '#10b981' : '#ef4444';

    const baselineY =
      height - paddingY - (((wallet?.initial_balance || 50) - minVal) / range) * (height - paddingY * 2);

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '170px', overflow: 'visible' }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Baseline initial balance */}
        <line
          x1={paddingX}
          y1={baselineY}
          x2={width - paddingX}
          y2={baselineY}
          stroke="rgba(255,255,255,0.15)"
          strokeDasharray="4 4"
        />

        {/* Area fill */}
        <polygon
          points={`${paddingX},${height - paddingY} ${points} ${width - paddingX},${height - paddingY}`}
          fill="url(#equityGrad)"
        />

        {/* Line */}
        <polyline
          fill="none"
          stroke={strokeColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />

        {/* First & Last Points */}
        {equityCurve.map((d, idx) => {
          if (idx === 0 || idx === equityCurve.length - 1) {
            const cx = paddingX + (idx / (equityCurve.length - 1)) * (width - paddingX * 2);
            const cy = height - paddingY - ((d.equity - minVal) / range) * (height - paddingY * 2);
            return (
              <circle
                key={idx}
                cx={cx}
                cy={cy}
                r="4.5"
                fill={strokeColor}
                stroke="#0f172a"
                strokeWidth="2"
              />
            );
          }
          return null;
        })}
      </svg>
    );
  };

  const initialBal = wallet?.initial_balance || 50.0;
  const balance = wallet?.balance || 50.0;
  const equity = wallet?.equity || 50.0;
  const floatingPnl = wallet?.floating_pnl || 0.0;
  const netProfit = wallet?.net_profit_usd || 0.0;
  const roi = wallet?.roi_percent || 0.0;
  const winRate = wallet?.win_rate || 0.0;
  const isAuto = wallet?.is_auto_trading ?? true;
  const freeMargin = wallet?.free_margin || 50.0;
  const usedMargin = wallet?.used_margin || 0.0;

  if (isLoading && !wallet) {
    return (
      <div style={{ padding: '80px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px', color: '#94a3b8' }}>
        <Loader2 size={36} className="animate-spin" color="#f59e0b" />
        <span style={{ fontSize: '15px', fontWeight: 600 }}>Đang nạp dữ liệu Ví Đầu Tư Ảo & MT5 Live...</span>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1440px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Toast Alert Notification */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '24px',
            zIndex: 9999,
            padding: '14px 20px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            background: toast.type === 'success' ? '#064e3b' : '#7f1d1d',
            border: `1px solid ${toast.type === 'success' ? '#10b981' : '#ef4444'}`,
            color: '#ffffff',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
            fontWeight: 600,
            fontSize: '14px',
            animation: 'slideIn 0.25s ease',
          }}
        >
          {toast.type === 'success' ? <CheckCircle2 size={18} color="#34d399" /> : <AlertCircle size={18} color="#f87171" />}
          <span>{toast.message}</span>
          <button
            onClick={() => setToast(null)}
            style={{ background: 'transparent', border: 'none', color: '#cbd5e1', cursor: 'pointer', padding: 0, marginLeft: '8px' }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* HEADER SECTION: Branding, Auto Status, Quick Actions */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '16px',
          padding: '22px 26px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '18px',
          backdropFilter: 'blur(16px)',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.25)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.35)',
            }}
          >
            <Wallet size={28} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '22px', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '-0.3px' }}>
                Ví Đầu Tư Ảo (Paper Trading Simulator)
              </h1>
              <div
                style={{
                  padding: '4px 10px',
                  borderRadius: '20px',
                  fontSize: '11px',
                  fontWeight: 700,
                  background: isAuto ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: isAuto ? '#10b981' : '#ef4444',
                  border: `1px solid ${isAuto ? '#10b981' : '#ef4444'}`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    background: isAuto ? '#10b981' : '#ef4444',
                    boxShadow: isAuto ? '0 0 10px #10b981' : 'none',
                    animation: isAuto ? 'pulse 2s infinite' : 'none',
                  }}
                />
                {isAuto ? 'AUTO TRADING BẬT' : 'AUTO TRADING ĐÃ DỪNG'}
              </div>
            </div>
            <p style={{ margin: '5px 0 0', fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
              Tự động khớp lệnh <b>0.01 lot</b> khi Bot phát tín hiệu M5, theo dõi giá Live MT5 và kiểm chứng lời/lỗ thời gian thực.
            </p>
          </div>
        </div>

        {/* Buttons Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Nút Bật/Tắt Auto Trading */}
          <button
            onClick={handleToggleAuto}
            disabled={isTogglingAuto}
            style={{
              padding: '11px 18px',
              borderRadius: '10px',
              border: `1px solid ${isAuto ? '#ef4444' : '#10b981'}`,
              background: isAuto ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
              color: isAuto ? '#ef4444' : '#10b981',
              fontWeight: 700,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: isTogglingAuto ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              opacity: isTogglingAuto ? 0.7 : 1,
            }}
          >
            {isTogglingAuto ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Đang xử lý...</span>
              </>
            ) : (
              <>
                <Power size={16} />
                <span>{isAuto ? 'Tạm Dừng Đi Lệnh' : 'Bật Tự Động Đi Lệnh'}</span>
              </>
            )}
          </button>

          {/* Nút Làm Mới */}
          <button
            onClick={() => loadWalletData(true)}
            disabled={isRefreshing}
            style={{
              padding: '11px 16px',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              background: 'rgba(255, 255, 255, 0.06)',
              color: '#f8fafc',
              fontWeight: 600,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: isRefreshing ? 'not-allowed' : 'pointer',
            }}
            title="Làm mới trạng thái ví và lệnh live"
          >
            {isRefreshing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                <span>Đang tải...</span>
              </>
            ) : (
              <>
                <RefreshCw size={15} />
                <span>Làm Mới</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* METRIC KPI CARDS (5 CỘT) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Card 1: Số Dư (Balance) */}
        <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>Số Dư (Balance)</span>
            <DollarSign size={17} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.5px' }}>
            ${balance.toFixed(2)} <span style={{ fontSize: '18px', color: '#f59e0b', fontWeight: 700 }}>U</span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            Vốn nạp ban đầu: <b style={{ color: '#cbd5e1' }}>${initialBal.toFixed(2)} U</b>
          </div>
        </div>

        {/* Card 2: Tài Sản Thực (Equity) */}
        <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>Tài Sản (Equity)</span>
            <Activity size={17} color="#3b82f6" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.5px' }}>
            ${equity.toFixed(2)} <span style={{ fontSize: '18px', color: '#3b82f6', fontWeight: 700 }}>U</span>
          </div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: floatingPnl >= 0 ? '#10b981' : '#ef4444', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            {floatingPnl >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            <span>Đang {floatingPnl >= 0 ? `lời +$${floatingPnl.toFixed(2)} (+${floatingPnl.toFixed(2)} U)` : `âm -$${Math.abs(floatingPnl).toFixed(2)} (-${Math.abs(floatingPnl).toFixed(2)} U)`}</span>
          </div>
        </div>

        {/* Card 3: Lợi Nhuận Ròng & ROI */}
        <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>Lãi / Lỗ Ròng</span>
            <TrendingUp size={17} color={netProfit >= 0 ? '#10b981' : '#ef4444'} />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: netProfit >= 0 ? '#10b981' : '#ef4444', letterSpacing: '-0.5px' }}>
            {netProfit >= 0 ? `+$${netProfit.toFixed(2)}` : `-$${Math.abs(netProfit).toFixed(2)}`} <span style={{ fontSize: '18px', fontWeight: 700 }}>U</span>
          </div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: roi >= 0 ? '#10b981' : '#ef4444', marginTop: '6px' }}>
            ROI: {roi >= 0 ? `+${roi.toFixed(1)}%` : `${roi.toFixed(1)}%`}
          </div>
        </div>

        {/* Card 4: Tỷ Lệ Thắng (Win Rate) */}
        <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>Tỷ Lệ Thắng</span>
            <Zap size={17} color="#8b5cf6" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.5px' }}>
            {winRate.toFixed(1)}%
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            <span style={{ color: '#10b981', fontWeight: 700 }}>{wallet?.winning_trades || 0}W</span> - <span style={{ color: '#ef4444', fontWeight: 700 }}>{wallet?.losing_trades || 0}L</span> ({wallet?.total_trades || 0} lệnh)
          </div>
        </div>

        {/* Card 5: Ký Quỹ Còn Dư (Free Margin) */}
        <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>Ký Quỹ Khả Dụng</span>
            <Sliders size={17} color="#06b6d4" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.5px' }}>
            ${freeMargin.toFixed(2)} <span style={{ fontSize: '18px', color: '#06b6d4', fontWeight: 700 }}>U</span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            Đang dùng: <b>${usedMargin.toFixed(2)} U</b> (Đòn bẩy 1:500)
          </div>
        </div>
      </div>

      {/* MIDDLE SECTION: 2 COLUMNS (CẤU HÌNH VỐN & BIỂU ĐỒ EQUITY CURVE) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 420px) 1fr', gap: '22px' }}>
        {/* CỘT TRÁI: BẢNG NẠP VỐN & CẤU HÌNH GIAO DỊCH */}
        <div
          style={{
            background: '#1e293b',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '14px' }}>
            <Sliders size={18} color="#f59e0b" />
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
              Thiết Lập Số Vốn & Quản Lý Ví
            </h3>
          </div>

          {/* Nút chọn nhanh vốn */}
          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '8px', display: 'block' }}>
              Chọn nhanh số tiền nạp ảo ($ USD):
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px' }}>
              {[50, 100, 200, 500, 1000].map((amt) => {
                const isSelected = depositAmount === String(amt);
                return (
                  <button
                    key={amt}
                    onClick={() => setQuickAmount(amt)}
                    style={{
                      padding: '8px 0',
                      borderRadius: '8px',
                      border: isSelected ? '1.5px solid #f59e0b' : '1px solid rgba(255,255,255,0.08)',
                      background: isSelected ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255,255,255,0.03)',
                      color: isSelected ? '#f59e0b' : '#cbd5e1',
                      fontWeight: 700,
                      fontSize: '13px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    ${amt}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Ô nhập số tiền tùy ý + nút cộng dồn */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>
                Số vốn tùy chỉnh:
              </label>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[10, 50, 100].map((step) => (
                  <button
                    key={step}
                    onClick={() => addAmount(step)}
                    style={{
                      padding: '2px 7px',
                      borderRadius: '4px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      background: 'rgba(255,255,255,0.04)',
                      color: '#94a3b8',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    +{step}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: '14px', top: '10px', color: '#f59e0b', fontWeight: 800, fontSize: '16px' }}>$</span>
              <input
                type="number"
                min="10"
                step="5"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px 10px 32px',
                  borderRadius: '10px',
                  background: 'rgba(15, 23, 42, 0.7)',
                  border: '1.5px solid rgba(255,255,255,0.15)',
                  color: '#f8fafc',
                  fontSize: '16px',
                  fontWeight: 700,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
                placeholder="50.00"
              />
            </div>
          </div>

          {/* Khối lượng vào lệnh */}
          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px', display: 'block' }}>
              Khối lượng mỗi lệnh (Lot Size):
            </label>
            <select
              value={lotSize}
              onChange={(e) => setLotSize(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '10px',
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#f8fafc',
                fontSize: '13px',
                fontWeight: 600,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            >
              <option value="0.01">0.01 lot (1 giá Vàng = $1.00 USD - Khuyến nghị cho $50-$100)</option>
              <option value="0.02">0.02 lot (Cho phép chốt lời 50% ở Tier 1)</option>
              <option value="0.05">0.05 lot (Dành cho tài khoản từ $500 trở lên)</option>
            </select>
          </div>

          {/* NÚT ÁP DỤNG SỐ VỐN VỚI LOADING SPINNER */}
          <button
            onClick={handleSetupWallet}
            disabled={isSettingUp}
            style={{
              padding: '13px',
              borderRadius: '10px',
              border: 'none',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '14px',
              cursor: isSettingUp ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 16px rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              opacity: isSettingUp ? 0.75 : 1,
              transition: 'all 0.2s',
            }}
          >
            {isSettingUp ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>Đang Cập Nhật Số Vốn...</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Áp Dụng Số Vốn ${depositAmount}</span>
              </>
            )}
          </button>

          {/* KHỞI TẠO LẠI VÍ (RESET) VỚI LOADING VÀ CONFIRM */}
          <div style={{ marginTop: 'auto', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            {!showResetConfirm ? (
              <button
                onClick={() => setShowResetConfirm(true)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '8px',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  background: 'rgba(239, 68, 68, 0.08)',
                  color: '#ef4444',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <RotateCcw size={14} />
                <span>Reset Ví Về Ban Đầu (${depositAmount})</span>
              </button>
            ) : (
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '10px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '12px', color: '#fca5a5', fontWeight: 600, textAlign: 'center' }}>
                  Xác nhận xóa hết lệnh và đưa số dư về <b>${depositAmount}</b>?
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleResetWallet}
                    disabled={isResetting}
                    style={{
                      flex: 1,
                      padding: '8px',
                      borderRadius: '6px',
                      border: 'none',
                      background: '#ef4444',
                      color: '#ffffff',
                      fontWeight: 700,
                      fontSize: '12px',
                      cursor: isResetting ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                    }}
                  >
                    {isResetting ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>Đang reset...</span>
                      </>
                    ) : (
                      <span>Đồng Ý Reset</span>
                    )}
                  </button>
                  <button
                    onClick={() => setShowResetConfirm(false)}
                    style={{
                      padding: '8px 14px',
                      borderRadius: '6px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      background: 'transparent',
                      color: '#cbd5e1',
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    Hủy
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* CỘT PHẢI: BIỂU ĐỒ TĂNG TRƯỞNG VỐN (EQUITY CURVE) */}
        <div
          style={{
            background: '#1e293b',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <TrendingUp size={18} color="#10b981" />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
                  Đường Tăng Trưởng Vốn (Equity Curve)
                </h3>
              </div>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                {equityCurve.length} mốc snapshot
              </span>
            </div>
            <p style={{ margin: '0 0 16px', fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
              Biểu đồ trực quan hóa tài sản thực tế biến động theo từng lệnh bot tự động chốt lời hoặc cắt lỗ.
            </p>
          </div>

          {/* Khung chứa SVG biểu đồ */}
          <div style={{ background: 'rgba(15, 23, 42, 0.5)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
            {renderEquityCurveSvg()}
          </div>

          {/* Chú thích biểu đồ */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px', fontSize: '12px', color: '#94a3b8' }}>
            <span>Đường chấm nét đứt: Vốn ban đầu (<b>${initialBal.toFixed(2)}</b>)</span>
            <span style={{ color: roi >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>
              Hiệu suất tài khoản: {roi >= 0 ? `+${roi.toFixed(1)}%` : `${roi.toFixed(1)}%`}
            </span>
          </div>
        </div>
      </div>

      {/* BOTTOM SECTION: TABBED VIEW CHO LỆNH ĐANG MỞ & LỊCH SỬ CHỐT */}
      <div
        style={{
          background: '#1e293b',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '24px',
        }}
      >
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '14px', marginBottom: '18px' }}>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => setActiveTab('positions')}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: activeTab === 'positions' ? '1px solid #3b82f6' : '1px solid transparent',
                background: activeTab === 'positions' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: activeTab === 'positions' ? '#38bdf8' : '#94a3b8',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Activity size={16} />
              <span>Lệnh Ảo Đang Mở ({positions.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('history')}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: activeTab === 'history' ? '1px solid #8b5cf6' : '1px solid transparent',
                background: activeTab === 'history' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
                color: activeTab === 'history' ? '#c084fc' : '#94a3b8',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <History size={16} />
              <span>Nhật Ký Các Lệnh Đã Chốt ({history.length})</span>
            </button>
          </div>

          <span style={{ fontSize: '12px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
            Đồng bộ MT5 Live
          </span>
        </div>

        {/* TAB 1: BẢNG LỆNH ĐANG MỞ (LIVE OPEN POSITIONS) */}
        {activeTab === 'positions' && (
          <div>
            {positions.length === 0 ? (
              <div
                style={{
                  padding: '42px 20px',
                  textAlign: 'center',
                  color: '#94a3b8',
                  background: 'rgba(15, 23, 42, 0.3)',
                  borderRadius: '12px',
                  fontSize: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <Layers size={28} color="#64748b" style={{ opacity: 0.6 }} />
                <span>Hiện chưa có lệnh nào đang chạy trên ví ảo.</span>
                <span style={{ fontSize: '12px', color: '#64748b' }}>
                  Khi Bot nhận diện setup M5 hợp lưu mới, lệnh <b>0.01 lot</b> sẽ tự động xuất hiện tại đây!
                </span>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: '#94a3b8' }}>
                      <th style={{ padding: '12px 10px' }}>Mã Lệnh</th>
                      <th style={{ padding: '12px 10px' }}>Cặp / Hướng</th>
                      <th style={{ padding: '12px 10px' }}>Khối Lượng</th>
                      <th style={{ padding: '12px 10px' }}>Giá Vào</th>
                      <th style={{ padding: '12px 10px' }}>Giá Hiện Tại</th>
                      <th style={{ padding: '12px 10px' }}>Stop Loss (Trailing)</th>
                      <th style={{ padding: '12px 10px' }}>Take Profit 1</th>
                      <th style={{ padding: '12px 10px', textAlign: 'right' }}>Lợi Nhuận Thả Nổi (U / USD)</th>
                      <th style={{ padding: '12px 10px', textAlign: 'center' }}>Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos) => {
                      const isBuy = pos.direction === 'BUY';
                      const isWin = pos.floating_pnl > 0;
                      const isLoss = pos.floating_pnl < 0;
                      const isClosingThis = closingPositionId === pos.position_id;
                      return (
                        <tr
                          key={pos.position_id}
                          style={{
                            borderBottom: '1px solid rgba(255,255,255,0.04)',
                            background: isWin ? 'rgba(16, 185, 129, 0.03)' : (isLoss ? 'rgba(239, 68, 68, 0.03)' : 'transparent'),
                          }}
                        >
                          <td style={{ padding: '14px 10px', fontWeight: 600, color: '#cbd5e1' }}>
                            <code>{pos.position_id}</code>
                          </td>
                          <td style={{ padding: '14px 10px' }}>
                            <span
                              style={{
                                padding: '3px 8px',
                                borderRadius: '4px',
                                fontWeight: 700,
                                fontSize: '11px',
                                background: isBuy ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                color: isBuy ? '#10b981' : '#ef4444',
                              }}
                            >
                              {pos.direction} {pos.symbol}
                            </span>
                          </td>
                          <td style={{ padding: '14px 10px', fontWeight: 600 }}>
                            {pos.volume.toFixed(2)} lot
                          </td>
                          <td style={{ padding: '14px 10px', fontWeight: 600, color: '#f8fafc' }}>
                            {pos.open_price.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', fontWeight: 700, color: '#38bdf8' }}>
                            {pos.current_price.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', color: '#fca5a5' }}>
                            {pos.stop_loss.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', color: '#86efac' }}>
                            {pos.take_profit_1.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', textAlign: 'right' }}>
                            <span
                              style={{
                                fontSize: '15px',
                                fontWeight: 800,
                                color: pos.floating_pnl >= 0 ? '#10b981' : '#ef4444',
                              }}
                            >
                              {pos.floating_pnl >= 0 ? `+$${pos.floating_pnl.toFixed(2)} (+${pos.floating_pnl.toFixed(2)} U)` : `-$${Math.abs(pos.floating_pnl).toFixed(2)} (-${Math.abs(pos.floating_pnl).toFixed(2)} U)`}
                            </span>
                          </td>
                          {/* NÚT ĐÓNG LỆNH CÓ LOADING RIÊNG */}
                          <td style={{ padding: '14px 10px', textAlign: 'center' }}>
                            <button
                              onClick={() => handleClosePosition(pos.position_id)}
                              disabled={isClosingThis}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '6px',
                                border: '1px solid rgba(239, 68, 68, 0.4)',
                                background: 'rgba(239, 68, 68, 0.1)',
                                color: '#ef4444',
                                fontSize: '12px',
                                fontWeight: 700,
                                cursor: isClosingThis ? 'not-allowed' : 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                              }}
                            >
                              {isClosingThis ? (
                                <>
                                  <Loader2 size={13} className="animate-spin" />
                                  <span>Đang đóng...</span>
                                </>
                              ) : (
                                <span>Đóng Ngay</span>
                              )}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: NHẬT KÝ LỆNH ĐÃ CHỐT (CLOSED TRADES HISTORY) */}
        {activeTab === 'history' && (
          <div>
            {history.length === 0 ? (
              <div
                style={{
                  padding: '42px 20px',
                  textAlign: 'center',
                  color: '#94a3b8',
                  background: 'rgba(15, 23, 42, 0.3)',
                  borderRadius: '12px',
                  fontSize: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <Clock size={28} color="#64748b" style={{ opacity: 0.6 }} />
                <span>Chưa có lệnh nào được chốt trong chu kỳ này.</span>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: '#94a3b8' }}>
                      <th style={{ padding: '12px 10px' }}>Mã Trade</th>
                      <th style={{ padding: '12px 10px' }}>Hướng / Cặp</th>
                      <th style={{ padding: '12px 10px' }}>Khối Lượng</th>
                      <th style={{ padding: '12px 10px' }}>Giá Vào</th>
                      <th style={{ padding: '12px 10px' }}>Giá Đóng</th>
                      <th style={{ padding: '12px 10px' }}>Lý Do Đóng</th>
                      <th style={{ padding: '12px 10px' }}>Pips</th>
                      <th style={{ padding: '12px 10px', textAlign: 'right' }}>Lợi Nhuận Đã Chốt (U / USD)</th>
                      <th style={{ padding: '12px 10px', textAlign: 'right' }}>Thời Gian Đóng</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((tr) => {
                      const isBuy = tr.direction === 'BUY';
                      return (
                        <tr key={tr.trade_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '12px 10px', color: '#94a3b8' }}>
                            <code>{tr.trade_id}</code>
                          </td>
                          <td style={{ padding: '12px 10px' }}>
                            <span
                              style={{
                                padding: '2px 7px',
                                borderRadius: '4px',
                                fontWeight: 700,
                                fontSize: '11px',
                                background: isBuy ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                color: isBuy ? '#10b981' : '#ef4444',
                              }}
                            >
                              {tr.direction} {tr.symbol}
                            </span>
                          </td>
                          <td style={{ padding: '12px 10px' }}>{tr.volume.toFixed(2)} lot</td>
                          <td style={{ padding: '12px 10px' }}>{tr.open_price.toFixed(2)}</td>
                          <td style={{ padding: '12px 10px', fontWeight: 600, color: '#f8fafc' }}>{tr.close_price.toFixed(2)}</td>
                          <td style={{ padding: '12px 10px' }}>
                            <span
                              style={{
                                padding: '3px 8px',
                                borderRadius: '12px',
                                fontSize: '11px',
                                fontWeight: 700,
                                background:
                                  tr.close_reason === 'TAKE_PROFIT'
                                    ? 'rgba(16, 185, 129, 0.15)'
                                    : tr.close_reason === 'STOP_LOSS'
                                    ? 'rgba(239, 68, 68, 0.15)'
                                    : 'rgba(245, 158, 11, 0.15)',
                                color:
                                  tr.close_reason === 'TAKE_PROFIT'
                                    ? '#10b981'
                                    : tr.close_reason === 'STOP_LOSS'
                                    ? '#ef4444'
                                    : '#f59e0b',
                              }}
                            >
                              {tr.close_reason}
                            </span>
                          </td>
                          <td style={{ padding: '12px 10px', color: tr.pnl_pips >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>
                            {tr.pnl_pips >= 0 ? `+${tr.pnl_pips.toFixed(1)}` : `${tr.pnl_pips.toFixed(1)}`}
                          </td>
                          <td style={{ padding: '12px 10px', textAlign: 'right', fontWeight: 800, color: tr.pnl_usd >= 0 ? '#10b981' : '#ef4444', fontSize: '14px' }}>
                            {tr.pnl_usd >= 0 ? `+$${tr.pnl_usd.toFixed(2)} (+${tr.pnl_usd.toFixed(2)} U)` : `-$${Math.abs(tr.pnl_usd).toFixed(2)} (-${Math.abs(tr.pnl_usd).toFixed(2)} U)`}
                          </td>
                          <td style={{ padding: '12px 10px', textAlign: 'right', color: '#64748b', fontSize: '12px' }}>
                            {tr.close_time ? new Date(tr.close_time).toLocaleTimeString() : '--'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
