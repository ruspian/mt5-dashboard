"""
Trade Journal
==============
Mengolah history deals MT5 (mt5.history_deals_get) menjadi:

1. Daftar "trade" lengkap — satu entri per posisi yang sudah closed,
   menggabungkan deal ENTRY (buka) dan deal OUT (tutup, termasuk partial
   close) jadi satu baris dengan entry price, exit price, durasi, dan
   profit bersih.

2. Statistik agregat — win rate, profit factor, rata-rata profit/loss,
   risk:reward realized, trade terbaik/terburuk, breakdown per hari.

SUMBER TRADE dibedakan lewat magic number:
  - magic 0 (atau tidak match apa pun) -> "manual" (dibuka lewat
    Terminal web atau langsung dari MT5)
  - magic == config.EA_MAGIC_NUMBER    -> "ea" (EA MQL5 lama)
  - magic == config.SIGNAL_MAGIC_NUMBER -> "signal" (Signal Engine)

CATATAN: MT5 mengelompokkan deal berdasarkan "position_id" (bukan
"order" biasa) untuk melacak siklus hidup satu posisi dari open sampai
closed, termasuk partial close di tengah jalan. Modul ini mengelompokkan
berdasarkan position_id supaya partial close (dari fitur TP1 di
signal_engine.py) tetap terhitung sebagai SATU trade dengan total
profit gabungan, bukan tercatat sebagai trade terpisah-pisah yang
menyesatkan statistik win rate.
"""

import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Optional

import MetaTrader5 as mt5

import config

log = logging.getLogger("trade-journal")


@dataclass
class JournalTrade:
    position_id: int
    symbol: str
    direction: str          # "BUY" | "SELL"
    source: str              # "manual" | "ea" | "signal"
    volume: float             # total volume yang closed (termasuk partial)
    entry_price: float
    exit_price: float         # volume-weighted average kalau ada partial close
    open_time: str
    close_time: str
    duration_minutes: float
    profit: float              # total profit bersih (termasuk semua partial close)
    commission: float
    swap: float
    net_profit: float          # profit + commission + swap
    is_win: bool
    magic: int
    comment: str

    def to_dict(self):
        return asdict(self)


def _classify_source(magic: int) -> str:
    if magic == config.SIGNAL_MAGIC_NUMBER:
        return "signal"
    if magic == config.EA_MAGIC_NUMBER and config.EA_MAGIC_NUMBER != 0:
        return "ea"
    return "manual"


def get_trades(days: int = 90) -> list[JournalTrade]:
    """Ambil & susun trade lengkap dari history deals MT5, dikelompokkan
    per position_id supaya partial close tidak pecah jadi banyak trade."""
    date_from = datetime.now() - timedelta(days=days)
    date_to = datetime.now() + timedelta(days=1)

    deals = mt5.history_deals_get(date_from, date_to)
    if deals is None:
        deals = []

    # Kelompokkan semua deal (in + out) per position_id
    positions: dict[int, list] = {}
    for d in deals:
        if d.type == mt5.DEAL_TYPE_BALANCE:
            continue  # deposit/withdrawal, bukan trade — sudah ditangani endpoint /history terpisah
        pos_id = d.position_id
        positions.setdefault(pos_id, []).append(d)

    trades = []
    for pos_id, group in positions.items():
        group.sort(key=lambda d: d.time)

        entry_deals = [d for d in group if d.entry == mt5.DEAL_ENTRY_IN]
        exit_deals = [d for d in group if d.entry == mt5.DEAL_ENTRY_OUT]

        if not entry_deals or not exit_deals:
            continue  # posisi belum sepenuhnya closed, atau data tidak lengkap — skip

        total_entry_volume = sum(d.volume for d in entry_deals)
        total_exit_volume = sum(d.volume for d in exit_deals)
        if total_entry_volume == 0 or total_exit_volume == 0:
            continue

        entry_price = sum(d.price * d.volume for d in entry_deals) / total_entry_volume
        exit_price = sum(d.price * d.volume for d in exit_deals) / total_exit_volume

        total_profit = sum(d.profit for d in group)
        total_commission = sum(d.commission for d in group)
        total_swap = sum(d.swap for d in group)
        net_profit = total_profit + total_commission + total_swap

        first_deal = entry_deals[0]
        last_deal = exit_deals[-1]
        # direction posisi: deal ENTRY_IN dengan type BUY berarti posisi BUY
        direction = "BUY" if first_deal.type == mt5.DEAL_TYPE_BUY else "SELL"

        magic = first_deal.magic
        comment = first_deal.comment or (exit_deals[0].comment if exit_deals else "")

        open_dt = datetime.fromtimestamp(first_deal.time)
        close_dt = datetime.fromtimestamp(last_deal.time)

        trades.append(
            JournalTrade(
                position_id=pos_id,
                symbol=first_deal.symbol,
                direction=direction,
                source=_classify_source(magic),
                volume=total_exit_volume,
                entry_price=round(entry_price, 5),
                exit_price=round(exit_price, 5),
                open_time=open_dt.isoformat(),
                close_time=close_dt.isoformat(),
                duration_minutes=round((close_dt - open_dt).total_seconds() / 60, 1),
                profit=round(total_profit, 2),
                commission=round(total_commission, 2),
                swap=round(total_swap, 2),
                net_profit=round(net_profit, 2),
                is_win=net_profit > 0,
                magic=magic,
                comment=comment,
            )
        )

    trades.sort(key=lambda t: t.close_time, reverse=True)
    return trades


@dataclass
class DailyBreakdown:
    date: str
    trades: int
    wins: int
    losses: int
    net_profit: float

    def to_dict(self):
        return asdict(self)


@dataclass
class JournalStats:
    total_trades: int
    wins: int
    losses: int
    win_rate: float              # persen, 0-100
    total_profit: float           # jumlah profit dari trade menang
    total_loss: float              # jumlah loss dari trade kalah (positif, bukan negatif)
    net_profit: float
    average_win: float
    average_loss: float            # positif
    profit_factor: Optional[float]  # total_profit / total_loss, None kalau total_loss=0
    average_rr: Optional[float]      # average_win / average_loss, None kalau average_loss=0
    best_trade: Optional[JournalTrade]
    worst_trade: Optional[JournalTrade]
    longest_win_streak: int = 0
    longest_loss_streak: int = 0
    current_streak: int = 0          # positif = sedang menang beruntun, negatif = sedang kalah beruntun
    daily_breakdown: list[DailyBreakdown] = field(default_factory=list)

    def to_dict(self):
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "net_profit": self.net_profit,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "profit_factor": self.profit_factor,
            "average_rr": self.average_rr,
            "best_trade": self.best_trade.to_dict() if self.best_trade else None,
            "worst_trade": self.worst_trade.to_dict() if self.worst_trade else None,
            "longest_win_streak": self.longest_win_streak,
            "longest_loss_streak": self.longest_loss_streak,
            "current_streak": self.current_streak,
            "daily_breakdown": [d.to_dict() for d in self.daily_breakdown],
        }


def _compute_streaks(trades_chronological: list[JournalTrade]) -> tuple[int, int, int]:
    """Hitung longest win streak, longest loss streak, dan streak saat ini.
    Input HARUS terurut kronologis (paling lama ke paling baru) — caller
    bertanggung jawab urutan ini, karena get_trades() sendiri mengembalikan
    urutan terbalik (terbaru dulu) untuk keperluan tampilan tabel."""
    longest_win = longest_loss = 0
    cur_win = cur_loss = 0

    for t in trades_chronological:
        if t.is_win:
            cur_win += 1
            cur_loss = 0
            longest_win = max(longest_win, cur_win)
        else:
            cur_loss += 1
            cur_win = 0
            longest_loss = max(longest_loss, cur_loss)

    current = cur_win if cur_win > 0 else -cur_loss
    return longest_win, longest_loss, current


def compute_by_source(trades: list[JournalTrade]) -> dict:
    """Breakdown statistik per sumber trade (manual/ea/signal), supaya
    kelihatan performa masing-masing sumber secara terpisah."""
    by_source: dict[str, list[JournalTrade]] = {}
    for t in trades:
        by_source.setdefault(t.source, []).append(t)

    result = {}
    for source, source_trades in by_source.items():
        wins = [t for t in source_trades if t.is_win]
        total = len(source_trades)
        net_profit = round(sum(t.net_profit for t in source_trades), 2)
        result[source] = {
            "trades": total,
            "wins": len(wins),
            "losses": total - len(wins),
            "win_rate": round(len(wins) / total * 100, 1) if total else 0.0,
            "net_profit": net_profit,
        }
    return result


def compute_stats(trades: list[JournalTrade]) -> JournalStats:
    """Hitung statistik agregat dari daftar trade. Semua pembagian
    dijaga dari division-by-zero — kalau tidak ada data yang cukup,
    field terkait diisi None, bukan error atau angka tidak masuk akal."""
    if not trades:
        return JournalStats(
            total_trades=0, wins=0, losses=0, win_rate=0.0,
            total_profit=0.0, total_loss=0.0, net_profit=0.0,
            average_win=0.0, average_loss=0.0,
            profit_factor=None, average_rr=None,
            best_trade=None, worst_trade=None,
            longest_win_streak=0, longest_loss_streak=0, current_streak=0,
            daily_breakdown=[],
        )

    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if not t.is_win]

    total_profit = sum(t.net_profit for t in wins)
    total_loss = abs(sum(t.net_profit for t in losses))  # dibuat positif untuk kemudahan baca & rasio
    net_profit = round(total_profit - total_loss, 2)

    win_rate = round(len(wins) / len(trades) * 100, 1) if trades else 0.0
    average_win = round(total_profit / len(wins), 2) if wins else 0.0
    average_loss = round(total_loss / len(losses), 2) if losses else 0.0

    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else None
    average_rr = round(average_win / average_loss, 2) if average_loss > 0 else None

    best_trade = max(trades, key=lambda t: t.net_profit) if trades else None
    worst_trade = min(trades, key=lambda t: t.net_profit) if trades else None

    # Streak dihitung dari urutan KRONOLOGIS (get_trades() return terbalik,
    # terbaru dulu, jadi di-reverse dulu di sini)
    trades_chronological = list(reversed(trades))
    longest_win_streak, longest_loss_streak, current_streak = _compute_streaks(trades_chronological)

    # Breakdown per hari (berdasarkan tanggal close_time)
    daily: dict[str, dict] = {}
    for t in trades:
        date_key = t.close_time[:10]  # "YYYY-MM-DD"
        d = daily.setdefault(date_key, {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0})
        d["trades"] += 1
        d["wins"] += 1 if t.is_win else 0
        d["losses"] += 0 if t.is_win else 1
        d["net_profit"] += t.net_profit

    daily_breakdown = [
        DailyBreakdown(date=date, trades=v["trades"], wins=v["wins"], losses=v["losses"], net_profit=round(v["net_profit"], 2))
        for date, v in sorted(daily.items(), reverse=True)
    ]

    return JournalStats(
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        total_profit=round(total_profit, 2),
        total_loss=round(total_loss, 2),
        net_profit=net_profit,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        average_rr=average_rr,
        best_trade=best_trade,
        worst_trade=worst_trade,
        longest_win_streak=longest_win_streak,
        longest_loss_streak=longest_loss_streak,
        current_streak=current_streak,
        daily_breakdown=daily_breakdown,
    )
