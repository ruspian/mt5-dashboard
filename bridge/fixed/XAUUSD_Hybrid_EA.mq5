//+------------------------------------------------------------------+
//|                                          XAUUSD_Hybrid_EA.mq5   |
//|   Trend-filtered entries + limited martingale + hard equity stop |
//|                                                                    |
//|   PENTING - BACA INI:                                            |
//|   EA ini menggunakan martingale (menggandakan lot saat rugi).    |
//|   Martingale punya risiko matematis "risk of ruin" - bukan       |
//|   kemungkinan, tapi kepastian jangka panjang jika parameter      |
//|   tidak dijaga ketat. Equity stop di bawah adalah pengaman       |
//|   terakhir, BUKAN jaminan profit. Uji di akun DEMO/CENT dulu     |
//|   minimal beberapa minggu sebelum pertimbangkan modal lebih      |
//|   besar. Tidak ada EA yang bisa menjamin profit di forex/gold.   |
//+------------------------------------------------------------------+
#property copyright "Educational EA - Use at your own risk"
#property version   "1.00"
#property strict

#define SIGNAL_FILE "ea_signal.txt"   // nama file, folder Common\Files
#define STATUS_FILE "ea_status.txt"

#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== Trend Filter ==="
input int      EMA_Fast_Period     = 20;       // EMA cepat (trend filter)
input int      EMA_Slow_Period     = 50;       // EMA lambat (trend filter)
input int      RSI_Period          = 14;       // RSI period
input double   RSI_Overbought      = 70.0;     // RSI overbought level
input double   RSI_Oversold        = 30.0;     // RSI oversold level

input group "=== Martingale Settings ==="
input double   Lot_Awal            = 0.01;     // Lot awal (level 1)
input double   Lot_Multiplier      = 1.5;      // Pengali lot tiap level
input int      Max_Level           = 5;        // Level martingale maksimal
input int      Jarak_Level_Points  = 300;      // Jarak antar level (points, XAUUSD 1 point = $0.01 biasanya)
input double   Max_Lot_Per_Order   = 1.0;      // Cap lot maksimal per order (safety)

input group "=== Risk Management ==="
input double   TakeProfit_USD      = 5.0;      // Target profit total basket (USD) untuk close semua
input double   Equity_Stop_Percent = 30.0;     // % floating loss dari balance awal -> EA stop total
input double   SL_Points_PerOrder  = 0;        // SL per order individual (0 = tidak pakai, andalkan equity stop + basket TP)
input int      Magic_Number        = 88123;    // Magic number
input string   Trade_Comment       = "XAU_Hybrid";

input group "=== Session Filter (opsional) ==="
input bool     Gunakan_Jam_Trading = false;    // Batasi jam trading?
input int      Jam_Mulai           = 7;        // Jam mulai (server time)
input int      Jam_Selesai         = 21;       // Jam selesai (server time)

//--- Global variables
int handleEmaFast, handleEmaSlow, handleRsi;
double balanceAwal = 0;
bool   eaStopped    = false;
ulong  levelSaatIni = 0;
datetime lastBarTime = 0;
datetime g_lastStatusWrite = 0;   // dipakai WriteEAStatus() untuk throttle penulisan file (fix: sebelumnya belum dideklarasikan)

//+------------------------------------------------------------------+
int OnInit()
{
   handleEmaFast = iMA(_Symbol, PERIOD_CURRENT, EMA_Fast_Period, 0, MODE_EMA, PRICE_CLOSE);
   handleEmaSlow = iMA(_Symbol, PERIOD_CURRENT, EMA_Slow_Period, 0, MODE_EMA, PRICE_CLOSE);
   handleRsi     = iRSI(_Symbol, PERIOD_CURRENT, RSI_Period, PRICE_CLOSE);

   if(handleEmaFast==INVALID_HANDLE || handleEmaSlow==INVALID_HANDLE || handleRsi==INVALID_HANDLE)
   {
      Print("ERROR: Gagal membuat indicator handle");
      return(INIT_FAILED);
   }

   balanceAwal = AccountInfoDouble(ACCOUNT_BALANCE);
   trade.SetExpertMagicNumber(Magic_Number);

   Print("=== EA XAUUSD Hybrid dimulai ===");
   Print("Balance awal: ", balanceAwal);
   Print("Equity stop akan aktif pada floating loss >= ", Equity_Stop_Percent, "% (", 
         balanceAwal * Equity_Stop_Percent / 100.0, " USD)");
   Print("PERINGATAN: EA ini menggunakan martingale. Pantau secara berkala.");

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handleEmaFast);
   IndicatorRelease(handleEmaSlow);
   IndicatorRelease(handleRsi);
}

//+------------------------------------------------------------------+
//| Hitung jumlah posisi EA ini yang sedang terbuka                  |
//+------------------------------------------------------------------+
int HitungPosisiTerbuka(double &totalProfit, double &avgPrice, double &totalLot, bool &isBuy)
{
   int count = 0;
   totalProfit = 0;
   totalLot = 0;
   double sumPriceLot = 0;

   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic_Number && PositionGetString(POSITION_SYMBOL) == _Symbol)
         {
            count++;
            totalProfit += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
            double lot = PositionGetDouble(POSITION_VOLUME);
            totalLot += lot;
            sumPriceLot += PositionGetDouble(POSITION_PRICE_OPEN) * lot;
            isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         }
      }
   }
   if(totalLot > 0) avgPrice = sumPriceLot / totalLot;
   else avgPrice = 0;

   return count;
}

bool IsTradingAllowed()
{
   int handle = FileOpen(SIGNAL_FILE, FILE_READ | FILE_TXT | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return true; // kalau file belum ada, default: boleh trading

   string content = "";
   if(!FileIsEnding(handle))
      content = FileReadString(handle);
   FileClose(handle);

   StringToUpper(content);
   StringTrimLeft(content);
   StringTrimRight(content);

   return (content != "STOP");
}


void WriteEAStatus(string statusText, string detail)
{
   // batasi penulisan tiap 5 detik biar tidak terlalu sering I/O ke disk
   if(TimeCurrent() - g_lastStatusWrite < 5)
      return;
   g_lastStatusWrite = TimeCurrent();

   int handle = FileOpen(STATUS_FILE, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return;

   string line = statusText + "|" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "|" + detail;
   FileWriteString(handle, line);
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Cek equity stop - proteksi utama                                  |
//+------------------------------------------------------------------+
bool CekEquityStop()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double floatingLossPercent = ((balanceAwal - equity) / balanceAwal) * 100.0;

   if(floatingLossPercent >= Equity_Stop_Percent)
   {
      Print("!!! EQUITY STOP TERPICU !!! Floating loss: ", 
            DoubleToString(floatingLossPercent,2), "% dari balance awal.");
      Print("Menutup SEMUA posisi dan menghentikan EA.");
      TutupSemuaPosisi();
      eaStopped = true;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void TutupSemuaPosisi()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic_Number && PositionGetString(POSITION_SYMBOL) == _Symbol)
         {
            trade.PositionClose(ticket);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Cek basket take profit                                           |
//+------------------------------------------------------------------+
void CekBasketTP()
{
   double totalProfit, avgPrice, totalLot;
   bool isBuy;
   int count = HitungPosisiTerbuka(totalProfit, avgPrice, totalLot, isBuy);

   if(count > 0 && totalProfit >= TakeProfit_USD)
   {
      Print("Basket TP tercapai: ", DoubleToString(totalProfit,2), " USD. Menutup semua posisi.");
      TutupSemuaPosisi();
      levelSaatIni = 0;
   }
}

//+------------------------------------------------------------------+
//| Sinyal trend filter                                              |
//+------------------------------------------------------------------+
int GetSignal()
{
   double emaFast[], emaSlow[], rsi[];
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow, true);
   ArraySetAsSeries(rsi, true);

   if(CopyBuffer(handleEmaFast, 0, 0, 3, emaFast) < 3) return 0;
   if(CopyBuffer(handleEmaSlow, 0, 0, 3, emaSlow) < 3) return 0;
   if(CopyBuffer(handleRsi, 0, 0, 3, rsi) < 3) return 0;

   // Trend naik: EMA fast > EMA slow, dan RSI belum overbought
   if(emaFast[0] > emaSlow[0] && rsi[0] < RSI_Overbought && rsi[0] > 50)
      return 1; // BUY

   // Trend turun: EMA fast < EMA slow, dan RSI belum oversold
   if(emaFast[0] < emaSlow[0] && rsi[0] > RSI_Oversold && rsi[0] < 50)
      return -1; // SELL

   return 0; // no signal
}

//+------------------------------------------------------------------+
bool DalamJamTrading()
{
   if(!Gunakan_Jam_Trading) return true;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(Jam_Mulai <= Jam_Selesai)
      return (dt.hour >= Jam_Mulai && dt.hour < Jam_Selesai);
   else
      return (dt.hour >= Jam_Mulai || dt.hour < Jam_Selesai);
}

//+------------------------------------------------------------------+
double HitungLot(int level)
{
   double lot = Lot_Awal * MathPow(Lot_Multiplier, level - 1);
   lot = MathMin(lot, Max_Lot_Per_Order);

   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathRound(lot / lotStep) * lotStep;
   lot = MathMax(lot, minLot);

   return lot;
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsTradingAllowed())
   {
      WriteEAStatus("STOPPED", "Dihentikan dari web dashboard");
      return;  // skip semua logic trading di bawah ini
   }
   WriteEAStatus("RUNNING", "Bot aktif normal");


   // Equity stop dicek SETIAP TICK - ini proteksi utama
   if(eaStopped) return;
   if(CekEquityStop()) return;

   CekBasketTP();

   double totalProfit, avgPrice, totalLot;
   bool isBuyPosisi;
   int jumlahPosisi = HitungPosisiTerbuka(totalProfit, avgPrice, totalLot, isBuyPosisi);

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   // --- Kalau belum ada posisi terbuka, cari entry baru berdasarkan sinyal trend ---
   if(jumlahPosisi == 0)
   {
      // hanya evaluasi sinyal sekali per bar baru biar tidak entry berulang di bar yang sama
      datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
      if(currentBarTime == lastBarTime) return;
      lastBarTime = currentBarTime;

      if(!DalamJamTrading()) return;

      int signal = GetSignal();
      if(signal == 0) return;

      double lot = HitungLot(1);
      levelSaatIni = 1;

      if(signal == 1)
         trade.Buy(lot, _Symbol, ask, 0, 0, Trade_Comment + "_L1");
      else
         trade.Sell(lot, _Symbol, bid, 0, 0, Trade_Comment + "_L1");

      return;
   }

   // --- Kalau sudah ada posisi, cek apakah perlu tambah level martingale ---
   if(jumlahPosisi >= Max_Level)
      return; // sudah mentok max level, tunggu TP atau equity stop

   double jarak = Jarak_Level_Points * point;

   if(isBuyPosisi)
   {
      // harga turun lebih jauh dari avgPrice -> tambah level BUY
      if(bid <= avgPrice - jarak)
      {
         int nextLevel = jumlahPosisi + 1;
         double lot = HitungLot(nextLevel);
         trade.Buy(lot, _Symbol, ask, 0, 0, Trade_Comment + "_L" + IntegerToString(nextLevel));
         levelSaatIni = nextLevel;
      }
   }
   else
   {
      // harga naik lebih jauh dari avgPrice -> tambah level SELL
      if(ask >= avgPrice + jarak)
      {
         int nextLevel = jumlahPosisi + 1;
         double lot = HitungLot(nextLevel);
         trade.Sell(lot, _Symbol, bid, 0, 0, Trade_Comment + "_L" + IntegerToString(nextLevel));
         levelSaatIni = nextLevel;
      }
   }
}
//+------------------------------------------------------------------+
