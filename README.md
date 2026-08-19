# Yuz tanish orqali davomat tizimi (Attendance CRM)

Hikvision IP kameralaridan RTSP oqimi orqali xodimlarning keldi/ketdi vaqtini
avtomatik qayd qiluvchi tizim. Alohida Face ID qurilmasi shart emas — mavjud
nazorat kameralari ishlatiladi.

Tizim tarkibida: xodimlar va bo'limlar boshqaruvi, davomat jurnali, statistika
(kechikish, ish soatlari, bo'limlar kesimi), jonli kamera oynasi va tizim
ko'rsatkichlari paneli.

## Tez boshlash (Docker — tavsiya etiladi)

```
cp .env.example .env      # kamera IP/login/parolini yozing
docker compose up -d
```
Brauzerda `http://localhost:5000`.

GPU'siz mashinada ishlatish uchun `docker-compose.yml` ichidagi `deploy.resources`
blokini o'chiring va `requirements.txt`da `onnxruntime-gpu` o'rniga
`onnxruntime` yozing (tanish sekinroq, lekin ishlaydi).

## Lokal o'rnatish (Docker'siz)

```
conda create -n attendance python=3.10 -y
conda activate attendance
pip install -r requirements.txt
python -m app.dashboard.app
```

To'liq NVIDIA CUDA Toolkit o'rnatish shart emas — `requirements.txt` tarkibidagi
`nvidia-*-cu12` paketlari kerakli CUDA/cuDNN DLL fayllarini o'zi bilan olib
keladi, `app/gpu_bootstrap.py` esa ularni ishga tushirishda PATH'ga qo'shadi.

GPU haqiqatan ishlatilayotganini tekshirish:
```
python scripts/smoke_test_gpu.py
```
Oxirida `providers in use: ['CUDAExecutionProvider', 'CPUExecutionProvider']`
chiqishi kerak. Faqat `CPUExecutionProvider` chiqsa — CUDA/cuDNN versiyalari
mos emas (kerak: CUDA 12.x + cuDNN 9.x).

## Sahifalar

| Sahifa | Vazifasi |
|---|---|
| Umumiy ko'rinish | Tanlangan kundagi davomat xulosasi |
| Xodimlar | Ro'yxat, bo'lim bo'yicha filtr, yangi xodim qo'shish (fayl yoki brauzer kamerasi orqali) |
| Bo'limlar | Dinamik bo'limlar, har biriga ish vaqti belgilash |
| Statistika | Davomat darajasi, kechikish, ish soatlari, 14 kunlik dinamika, bo'limlar kesimi |
| Davomat jurnali | Sana/xodim bo'yicha filtrlanadigan to'liq tarix |
| Jonli kamera | Real-vaqtda tanish oynasi; ko'rilgan xodimlar avtomatik davomatga yoziladi |
| Tizim | Kameralar holati, FPS, model sozlamalari, GPU/CPU holati |

## Sozlash

### Kameralarni qo'shish (tavsiya etiladigan yo'l)

Kameralar bazada saqlanadi va **"Kameralar" sahifasi** orqali boshqariladi.
Forma IP manzil, port, foydalanuvchi nomi, parol va oqim turini alohida
so'raydi — RTSP manzilini qo'lda yozish shart emas:

- Parol bazada alohida ustunda saqlanadi va manzilga foiz-kodlangan holda
  qo'shiladi, shuning uchun `@`, `:`, `/` kabi belgili parollar ham ishlaydi.
- Parol UI'da hech qachon ochiq ko'rsatilmaydi; tahrirlashda maydonni bo'sh
  qoldirsangiz saqlangan parol o'zgarmaydi.
- Ishlab chiqaruvchi (Hikvision/Dahua/Reolink/Uniview) tanlansa oqim yo'li
  avtomatik qo'yiladi; "Boshqa" tanlansa yo'l qo'lda kiritiladi.
- **Tarmoqni skanerlash** — lokal tarmoqdagi RTSP qurilmalarini topadi.
- **Kameralarni aniqlash** — kompyuterga ulangan kameralarni topadi va
  backend bilan birga (masalan `DSHOW №1`) ko'rsatadi. Windows'da bir xil
  raqam har backendda boshqa qurilmani bildirgani uchun ikkalasi birga
  saqlanadi.

### config.yaml

`app/config/config.yaml` faqat **birinchi ishga tushirishdagi boshlang'ich
qiymat** (baza bo'sh bo'lsa) va asosiy qoidalar uchun:

- `source_type: "webcam"` — lokal kompyuter kamerasi (tarmoqsiz sinov uchun,
  `device_index: 0`, ixtiyoriy `backend: "msmf"` yoki `"dshow"`)
- `source_type: "rtsp"` — tarmoq kamerasi. Ikki shakl qo'llanadi:
  qismlarga ajratilgan (`host`, `port`, `username`, `password`, `stream_path`)
  yoki tayyor `rtsp_url: "rtsp://user:pass@ip:554/Streaming/Channels/102"` —
  ikkinchisi bazaga ko'chirilayotganda avtomatik qismlarga ajratiladi.
  Hikvision'da kanal `102` — kichik oqim, tezroq ishlaydi; `101` — asosiy oqim.
- `recognition.similarity_threshold` — tanish qattiqligi (0.35–0.45). Past qiymat
  ko'zoynak/yon qarashda ham taniydi, lekin xato tanish xavfi ortadi.
- `attendance.debounce_seconds` — bitta xodim uchun ketma-ket yozuvlar orasidagi
  minimal vaqt

Standart holatda `pc_webcam` yoqilgan (tarmoqsiz darhol sinash uchun). Haqiqiy
kameraga o'tish uchun uni izohga oling va RTSP kamerani yoqing — bir nechta
kamera parallel ishlaydi.

### Muhit o'zgaruvchilari (env vars)

Docker/AWS uchun `config.yaml` qiymatlarini ustidan yozadi — parollarni kodga
yozmaslik uchun ishlatiladi:

| O'zgaruvchi | Vazifasi |
|---|---|
| `DATA_DIR` | Baza, yuz rasmlari va loglar uchun yagona papka (Docker volume) |
| `DATABASE_URL` | To'liq SQLAlchemy URL — AWS RDS PostgreSQL uchun |
| `CAMERAS_JSON` | Kameralar ro'yxati JSON formatida (config.yaml'ni to'liq almashtiradi) |
| `SIMILARITY_THRESHOLD`, `MODEL_NAME`, `FRAME_SKIP` | Model sozlamalari |
| `DEBOUNCE_SECONDS` | Davomat qoidasi |
| `DASHBOARD_HOST`, `DASHBOARD_PORT` | Server manzili |

## AWS'ga o'rnatish

Loyiha bulutga ko'chirishga tayyor qilib yozilgan:

1. **Hisoblash** — GPU kerak bo'lsa `g4dn.xlarge` (NVIDIA T4) EC2 instansiyasi;
   CPU rejimida `t3.large` ham yetadi (kam kamera uchun).
2. **Baza** — `DATABASE_URL` orqali RDS PostgreSQL'ga ulang; SQLite faqat bitta
   mashinada ishlash uchun mos.
   ```
   DATABASE_URL=postgresql+psycopg2://user:parol@endpoint:5432/attendance
   ```
   `psycopg2-binary` `requirements.txt`da allaqachon bor.
3. **Fayllar** — `DATA_DIR` uchun EBS volume ulang (yoki yuz rasmlarini S3'ga
   ko'chirish kerak bo'lsa `photo_path` saqlash joyini o'zgartiring).
4. **Tarmoq** — kameralar lokal tarmoqda bo'lgani uchun VPN (Site-to-Site yoki
   OpenVPN) kerak bo'ladi; muqobil variant — tanish ish joyida (edge), faqat
   natijalar bulutga yuboriladi.
5. **Ishga tushirish** — `docker compose up -d` yoki ECS/Fargate (GPU kerak
   bo'lsa ECS EC2 launch type).

## Telegram bot

Barcha dashboard imkoniyatlari (umumiy holat, statistika, xodimlar, bo'limlar,
davomat jurnali, kameralar, tizim) — Telegram botda ham, faqat tugmalar orqali
boshqariladi. Bundan tashqari **jonli bildirishnoma**: xodim kirish kamerasida
tanilib KELDI/KETDI yozilganda, bot obuna bo'lgan foydalanuvchilarga darhol
xabar yuboradi — kim, qachon, qaysi kamera/bo'lim.

### Sozlash

1. Telegram'da [@BotFather](https://t.me/BotFather) bilan `/newbot` — token oling.
2. O'z Telegram `user_id`'ingizni bilish uchun [@userinfobot](https://t.me/userinfobot)
   ga `/start` yozing (yoki botni tokensiz ishga tushirsangiz ham, ruxsatsiz
   foydalanuvchi `/start` bosganda bot unga o'z ID'sini ko'rsatadi).
3. `.env` faylida:
   ```
   TELEGRAM_BOT_TOKEN=<BotFather bergan token>
   TELEGRAM_ADMIN_IDS=<sizning user_id, kerak bo'lsa vergul bilan bir nechta>
   ```
   **`TELEGRAM_ADMIN_IDS` bo'sh bo'lsa — hech kim botdan foydalana olmaydi**
   (xavfsiz sukut holat: davomat ma'lumotlari nozik, tasodifan hammaga ochiq
   qolmasligi kerak).

### Menyu

| Tugma | Nima ko'rsatadi |
|---|---|
| 📊 Umumiy holat | Bugungi davomat foizi, keldi/kelmadi/kechikdi, o'rtacha ish vaqti |
| 📈 Statistika | Bo'limlar kesimi + oxirgi 7 kunlik dinamika |
| 👥 Xodimlar | Faol xodimlar ro'yxati, bo'lim va lavozim bilan |
| 🏢 Bo'limlar | Har bir bo'lim uchun ish vaqti va bugungi davomat |
| 📋 Davomat jurnali | Bugungi keldi/ketdi yozuvlari, sahifalab, har biri qaysi kamera aniqlaganini ko'rsatadi |
| 📷 Kameralar | Har bir kameraning jonli holati (ulangan/ulanmagan, FPS, tanilgan yuzlar) — dashboard'dan real vaqtda olinadi |
| ⚙️ Tizim | GPU/model holati, xodim va yozuv soni, kuzatuv xizmati uptime'i |
| 🔔 Bildirishnomalar | Jonli xabarlarni yoqish/o'chirish (davomat — sukut yoqiq; harakat/kuzatuv — sukut o'chiq, tez-tez bo'lgani uchun) |

### Arxitektura

Bot **alohida, yengil konteynerda** ishlaydi — GPU, OpenCV yoki InsightFace
kerak emas:
- Xodimlar/davomat ma'lumotlarini bazadan **bevosita** o'qiydi (`app.db`,
  `app.analytics` — dashboard bilan bir xil kod, ikki marta yozilmagan).
- Kamera **jonli** holatini (FPS, ulanganmi) dashboard'ning
  `/system/metrics.json` API'sidan HTTP orqali oladi — bu ma'lumot faqat
  kuzatuv xizmati ishlayotgan jarayonning xotirasida bor.
- Yangi davomat/harakat hodisalarini har 3 soniyada (`BOT_POLL_INTERVAL`)
  bazadan tekshirib, obunachilarga yuboradi. Qayta ishga tushirilganda eski
  hodisalarni qayta yubormaydi (oxirgi yuborilgan ID saqlanadi).

## CLI skriptlari

```
# Xodimni terminal orqali ro'yxatga olish
python -m app.recognition.enroll --name "Aziz Karimov" --code "EMP001" --image "photo.jpg"

# Barcha kameralarni fon xizmati sifatida ishga tushirish (dashboard'siz)
python -m app.main

# Demo ma'lumot yaratish / tozalash (UI sinovi uchun)
python scripts/seed_demo.py
python scripts/seed_demo.py --clear
```

Eslatma: `app.main` va dashboard'ning "Jonli kamera" sahifasi bir xil webcam
qurilmasini bir vaqtda ocholmaydi — ikkisidan faqat bittasini ishlating.

## Qanday ishlaydi

1. Har bir kamera uchun alohida thread video oqimini o'qiydi va faqat eng
   oxirgi kadrni saqlaydi (kechikishning oldini olish uchun).
2. Har kadrdan InsightFace (GPU) yordamida yuzlar aniqlanadi va 512 o'lchamli
   embedding chiqariladi.
3. Embedding bazadagi xodimlar bilan cosine similarity orqali solishtiriladi;
   `similarity_threshold`dan yuqori bo'lsa — tanildi.
4. Tanilgan xodim uchun oxirgi hodisa turiga qarab (keldi/ketdi) yangi yozuv
   `debounce_seconds` oralig'idan keyin bazaga qo'shiladi.
5. Kechikish va ish soatlari xodim bo'limiga belgilangan ish vaqtiga nisbatan
   hisoblanadi (`app/analytics.py`).

## Docker'da to'liq ishga tushirish (dashboard + bot + PostgreSQL)

`docker-compose.yml` uch xizmatni birga ishga tushiradi:

| Xizmat | Vazifasi | Talab |
|---|---|---|
| `postgres` | Umumiy baza | — |
| `dashboard` | Veb-panel + GPU kuzatuv xizmati | NVIDIA GPU + [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) |
| `bot` | Telegram bot | Faqat tarmoq — GPU kerak emas |

**Nega PostgreSQL, SQLite emas?** Uch jarayon (dashboard, kuzatuv worker'i,
bot) bir vaqtda bazaga yozadi/o'qiydi. SQLite bir nechta jarayondan bir vaqtda
yozishga yaxshi chidamaydi (fayl darajasida qulflanadi) — yuklama ortganда
"database is locked" xatolariga olib keladi. PostgreSQL bunga mo'ljallangan.

```
cp .env.example .env
# .env faylida to'ldiring: POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_IDS
docker compose up -d --build
```

Birinchi marta ishga tushirilganda `dashboard` bazani yaratadi va
`config.yaml`dagi boshlang'ich kamerani ko'chiradi; qolgan kameralarni
"Kameralar" sahifasidan qo'shing (login/parol alohida kiritiladi — xavfsiz).

**Eslatma — lokal SQLite'dan Postgres'ga o'tish:** agar avval lokal (SQLite)
rejimda kameralar/xodimlar qo'shgan bo'lsangiz, ular Postgres'ga avtomatik
ko'chmaydi (ikkalasi mustaqil baza). Kameralarni "Kameralar" sahifasidan
qayta qo'shish kifoya (bir necha daqiqa ish).

Loglarni ko'rish: `docker compose logs -f bot` yoki `docker compose logs -f dashboard`.

## Unumdorlik: Big-O va issiqlik/yuklama

| Qism | Murakkablik | Izoh |
|---|---|---|
| Xodimni tanish (`FaceMatcher.best`) | O(N·D), vektorlashgan (NumPy/BLAS matritsa ko'paytmasi) | 10 000 xodimda ham <1.1ms/yuz — cosine similarity uchun optimal, ANN indeks (FAISS) faqat o'n minglab xodimda kerak bo'ladi |
| Kadr qayta ishlash | Har kamera uchun faqat **yangi** kadr qayta ishlanadi (ketma-ket raqamlanadi) | Oldin muzlab qolgan kadr GPU'ga qayta-qayta yuborilardi — endi yo'q, bu asosiy GPU/issiqlik omili edi |
| Begona (mehmon) tanish | O(1) amortizatsiyalangan — xotiradagi kesh, 20s da yangilanadi | Oldin har begona yuz uchun BAZADAGI BARCHA mehmonlarni qayta o'qirdi |
| Statistika dinamikasi (`daily_trend`) | O(1) so'rov (butun oyna bir marta olinadi) | Oldin har kun uchun alohida so'rov (14 kun = 28+ so'rov) |

**Laptop qizib ketmaydimi?** 4 kamera bir vaqtda ishlaganda o'lchandi:
RTX 3050 Laptop GPU'da **68°C, ~28W, ~48% yuklama** — laptop GPU'lar odatda
~87–90°C'да throttling qiladi, ya'ni bu ancha xavfsiz oraliqda. CPU yuklamasi
~58% (jami tizim), xotira ~1.2GB. Agar ko'proq kamera qo'shilsa, `FRAME_SKIP`
qiymatini oshirish (kamroq kadr tahlil qilinadi) yoki `buffalo_sc` (tezroq,
kamroq aniq) modelga o'tish issiqlikni yanada kamaytiradi.

**Yuklamani ko'tarish uchun:** kuzatuv xizmati (`MultiCameraService`) va GPU
modeli bitta jarayonda, singleton — bu ataylab shunday (bitta GPU'ni bir
nechta jarayon bo'lishishi mumkin emas). Gorizontal kengayish shu bosqichda
bot va dashboard'ni **ajratishdan** keladi (allaqachon qilingan): bot HTTP
so'rovlari va Telegram trafigi GPU jarayoniga umuman ta'sir qilmaydi, va
PostgreSQL bir nechta yozuvchi/o'quvchini SQLite'dan farqli xavfsiz ko'taradi.

## Loyiha tuzilmasi

```
app/
  analytics.py           davomat hisob-kitoblari (kechikish, ish soatlari)
  attendance.py          keldi/ketdi logikasi (debounce, in/out almashish)
  gpu_bootstrap.py       CUDA/cuDNN DLL yo'llarini ro'yxatdan o'tkazish
  main.py                CLI runner (barcha kameralar, dashboard'siz)
  cameras/               RTSP va webcam oqimi
  config/                sozlamalar (YAML + env vars)
  db/                    SQLAlchemy modellari va ulanish
  recognition/           yuz aniqlash va tanish (InsightFace)
  dashboard/
    app.py               Flask ilovasi (blueprint'lar ro'yxatga olinadi)
    live.py              jonli kamera monitori va ko'rsatkichlari
    routes/              har bir sahifa alohida modul
    templates/           HTML shablonlar
bot/                      Telegram bot (yengil, GPU kerak emas)
  main.py                 kirish nuqtasi, botni ishga tushiradi
  handlers.py             buyruq/tugma bosish handler'lari + ruxsat tekshiruvi
  formatters.py           xabar matnlari (app.analytics'dan foydalanadi)
  keyboards.py            inline tugmali menyular
  notifier.py             yangi hodisalarni kuzatib jonli xabar yuboruvchi fon vazifasi
  dashboard_client.py     dashboard'ning /system/metrics.json'iga HTTP so'rov
  Dockerfile              yengil (python:slim) image
scripts/                 sinov va demo skriptlari
```
