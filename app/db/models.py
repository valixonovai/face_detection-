import json
from datetime import datetime, time

from sqlalchemy import String, Integer, Boolean, DateTime, Time, Date, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app import timeutil
from app.cameras.rtsp import DEFAULT_RTSP_PORT, build_rtsp_url, mask_url


class Base(DeclarativeBase):
    pass


# Kamera rollari
ROLE_ENTRANCE = "entrance"    # kirish/chiqish eshigi — davomat yozadi, begonalarni ham qayd qiladi
ROLE_MONITORING = "monitoring"  # koridor/xona — faqat "kim qayerda edi" harakat yozuvi

# Kirish kamerasining yo'nalishi
DIRECTION_IN = "in"
DIRECTION_OUT = "out"
DIRECTION_AUTO = "auto"  # yo'nalish noma'lum — keldi/ketdi navbat bilan almashadi


class Camera(Base):
    __tablename__ = "cameras"

    # Kalit sifatida qisqa slug ishlatiladi (masalan "entrance_main") — davomat
    # yozuvlarida shu saqlanadi, shuning uchun barqaror bo'lishi kerak.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "rtsp" | "webcam"
    device_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Lokal kamera uchun OpenCV backendi: "msmf" | "dshow" | "any".
    # Indeks raqami faqat shu backend doirasida ma'noga ega, shuning uchun
    # ikkalasi birga saqlanadi. Bo'sh bo'lsa — navbat bilan sinaladi.
    backend: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # RTSP ulanishi qismlarga ajratilgan holda saqlanadi: parol manzil ichida
    # emas, alohida ustunda turadi va UI'da hech qachon ochiq ko'rsatilmaydi.
    # Manzilning o'zi `resolved_rtsp_url()` orqali yig'iladi.
    host: Mapped[str | None] = mapped_column(String(160), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stream_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "main" | "sub"
    stream_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Eski (qismlarga ajratilmagan) yozuvlar uchun. Yangi kameralarda bo'sh —
    # `host` to'ldirilgan bo'lsa manzil har safar qismlardan yig'iladi.
    rtsp_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_MONITORING)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default=DIRECTION_AUTO)
    # Kuzatuv kameralari uchun joy nomi: "2-qavat koridori", "Yig'ilish xonasi"
    zone: Mapped[str | None] = mapped_column(String(160), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now)

    def resolved_rtsp_url(self) -> str | None:
        """Ulanish uchun to'liq manzil — login/paroli kodlangan holda."""
        if self.source_type != "rtsp":
            return None
        if self.host:
            return build_rtsp_url(
                self.host, self.port, self.username, self.password, self.stream_path
            )
        return self.rtsp_url  # qismlarga ajratilmagan eski yozuv

    def as_stream_config(self) -> dict:
        """CameraStream.from_config uchun konfiguratsiya."""
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "rtsp_url": self.resolved_rtsp_url(),
            "device_index": self.device_index,
            "backend": self.backend,
        }

    @property
    def source_label(self) -> str:
        """UI uchun qisqa tavsif — parol hech qachon ko'rsatilmaydi."""
        if self.source_type == "webcam":
            suffix = f" ({self.backend.upper()})" if self.backend else ""
            return f"qurilma #{self.device_index}{suffix}"
        if self.host:
            user = f"{self.username}@" if self.username else ""
            return f"{user}{self.host}:{self.port or DEFAULT_RTSP_PORT}{self.stream_path or '/'}"
        return mask_url(self.rtsp_url)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Kechikish/erta ketishni hisoblash uchun kutilayotgan ish vaqti (ixtiyoriy)
    expected_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    expected_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now)

    employees: Mapped[list["Employee"]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=True)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    photo_path: Mapped[str] = mapped_column(String(500), nullable=True)

    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hired_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active | inactive

    created_at: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now)

    department: Mapped["Department | None"] = relationship(back_populates="employees")
    # Xodim o'chirilsa uning davomat yozuvlari ham o'chadi (yozuv egasiz qololmaydi).
    # Tarixni saqlab qolish kerak bo'lsa o'chirish emas, "faolsizlantirish" ishlatiladi.
    logs: Mapped[list["AttendanceLog"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    presence_events: Mapped[list["PresenceEvent"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    def embedding(self) -> list[float]:
        return json.loads(self.embedding_json)


class AttendanceLog(Base):
    """Davomat hodisasi — faqat kirish (entrance) rolidagi kameralardan yoziladi."""

    __tablename__ = "attendance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(8), nullable=False)  # "in" | "out"
    similarity: Mapped[float] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now, index=True)

    employee: Mapped["Employee"] = relationship(back_populates="logs")


class Visitor(Base):
    """
    Tanilmagan (begona) odam. Kirish kamerasi har bir odamni qayd qiladi —
    xodim bo'lmasa ham. Takroriy ko'rinishlar embedding o'xshashligi orqali
    bitta mehmonga birlashtiriladi (har safar yangi yozuv yaratilmaydi).
    """

    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)  # "Mehmon #3"
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    first_seen: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now, index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now, index=True)
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    sightings: Mapped[list["PresenceEvent"]] = relationship(
        back_populates="visitor", cascade="all, delete-orphan"
    )

    def embedding(self) -> list[float]:
        return json.loads(self.embedding_json)


class PresenceEvent(Base):
    """
    "Kim qayerda edi" yozuvi — kuzatuv (monitoring) kameralaridan, hamda
    kirish kamerasida ko'rilgan begonalar uchun. Davomatga ta'sir qilmaydi.

    employee_id yoki visitor_id dan bittasi to'ldiriladi.
    """

    __tablename__ = "presence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    visitor_id: Mapped[int | None] = mapped_column(ForeignKey("visitors.id"), nullable=True)

    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone: Mapped[str | None] = mapped_column(String(160), nullable=True)
    similarity: Mapped[float] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=timeutil.now, index=True)

    employee: Mapped["Employee | None"] = relationship(back_populates="presence_events")
    visitor: Mapped["Visitor | None"] = relationship(back_populates="sightings")
