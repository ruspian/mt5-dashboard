//+------------------------------------------------------------------+
//| SNIPPET: Kontrol EA dari Web Dashboard                            |
//| ------------------------------------------------------------------|
//| Cara pakai: copy-paste bagian-bagian di bawah ini ke EA lo yang   |
//| sudah ada, di posisi yang ditandai. INI BUKAN FILE EA LENGKAP —   |
//| ini cuma potongan kode yang perlu ditempel ke EA existing lo.     |
//+------------------------------------------------------------------+

//--- 1) TARUH DI BAGIAN PALING ATAS (setelah #property, sebelum OnInit)
#define SIGNAL_FILE "ea_signal.txt"   // nama file, folder Common\Files
#define STATUS_FILE "ea_status.txt"

datetime g_lastStatusWrite = 0;

//--- 2) FUNGSI BARU: taruh di mana saja di dalam file EA lo (di luar fungsi lain)

// Baca perintah dari web. Return true kalau EA boleh trading (START),
// false kalau harus berhenti (STOP).
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

// Tulis status EA saat ini ke file, supaya web bisa menampilkannya.
// Panggil ini secara berkala (misalnya tiap tick, dibatasi tiap beberapa detik).
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

//--- 3) TARUH DI DALAM OnTick(), DI BARIS PALING ATAS (sebelum logic bot lo)
//
// void OnTick()
// {
//    if(!IsTradingAllowed())
//    {
//       WriteEAStatus("STOPPED", "Dihentikan dari web dashboard");
//       return;  // skip semua logic trading di bawah ini
//    }
//    WriteEAStatus("RUNNING", "Bot aktif normal");
//
//    // ... logic trading EA lo yang sudah ada, lanjut di sini seperti biasa ...
// }

//+------------------------------------------------------------------+
//| CATATAN PENTING                                                   |
//+------------------------------------------------------------------+
// 1. FILE_COMMON artinya file disimpan di folder bersama semua        
//    terminal MT5 di komputer itu, biasanya di:                      
//    C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\Common\Files\
//    Ini HARUS SAMA dengan path yang dipakai bridge Python             
//    (lihat config.py -> EA_SIGNAL_FILE dan EA_STATUS_FILE).           
//                                                                      
// 2. Setelah edit EA, compile ulang (F7 di MetaEditor) dan attach     
//    ulang EA ke chart supaya perubahan aktif.                        
//                                                                      
// 3. "STOP" hanya menghentikan EA membuka posisi BARU. Posisi yang    
//    sudah terbuka TIDAK otomatis ditutup. Kalau lo mau STOP juga     
//    menutup semua posisi bot, tambahkan logic close di bagian        
//    if(!IsTradingAllowed()) sebelum return — kasih tau saya kalau    
//    mau saya bantu tambahkan itu juga.                                
//+------------------------------------------------------------------+
