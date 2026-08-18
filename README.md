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
   PostgreSQL uchun `psycopg2-binary` paketini qo'shish kerak.
3. **Fayllar** — `DATA_DIR` uchun EBS volume ulang (yoki yuz rasmlarini S3'ga
   ko'chirish kerak bo'lsa `photo_path` saqlash joyini o'zgartiring).
4. **Tarmoq** — kameralar lokal tarmoqda bo'lgani uchun VPN (Site-to-Site yoki
   OpenVPN) kerak bo'ladi; muqobil variant — tanish ish joyida (edge), faqat
   natijalar bulutga yuboriladi.
5. **Ishga tushirish** — `docker compose up -d` yoki ECS/Fargate (GPU kerak
   bo'lsa ECS EC2 launch type).

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

## Loyiha tuzilmasi

```
app/
  analytics.py           davomat hisob-kitoblari (kechikish, ish soatlari)
  attendance.py          keldi/ketdi logikasi (debounce, in/out almashish)
  gpu_bootstrap.py       CUDA/cuDNN DLL yo'llarini ro'yxatdan o'tkazish
  main.py                CLI runner (barcha kameralar)
  cameras/               RTSP va webcam oqimi
  config/                sozlamalar (YAML + env vars)
  db/                    SQLAlchemy modellari va ulanish
  recognition/           yuz aniqlash va tanish (InsightFace)
  dashboard/
    app.py               Flask ilovasi (blueprint'lar ro'yxatga olinadi)
    live.py              jonli kamera monitori va ko'rsatkichlari
    routes/              har bir sahifa alohida modul
    templates/           HTML shablonlar
scripts/                 sinov va demo skriptlari
```
