"""
Inline tugmali menyular. Har bir funksiya foydalanuvchiga ko'rsatiladigan
tugmalar to'plamini qaytaradi — matnli buyruqlar emas, hammasi bosish orqali.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📊 Umumiy holat", callback_data="overview"),
            InlineKeyboardButton("📈 Statistika", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("👥 Xodimlar", callback_data="employees"),
            InlineKeyboardButton("🏢 Bo'limlar", callback_data="departments"),
        ],
        [
            InlineKeyboardButton("📋 Davomat jurnali", callback_data="log:0"),
            InlineKeyboardButton("📷 Kameralar", callback_data="cameras"),
        ],
        [
            InlineKeyboardButton("⚙️ Tizim", callback_data="system"),
            InlineKeyboardButton("🔔 Bildirishnomalar", callback_data="notify"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def back_to_menu(extra_row: list[InlineKeyboardButton] | None = None) -> InlineKeyboardMarkup:
    rows = [extra_row] if extra_row else []
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def refresh_and_back(callback: str) -> InlineKeyboardMarkup:
    return back_to_menu([InlineKeyboardButton("🔄 Yangilash", callback_data=callback)])


def departments_list(departments: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """departments: [(id, name), ...] — har biri alohida qatorda."""
    rows = [
        [InlineKeyboardButton(f"🏢 {name}", callback_data=f"dept:{dept_id}")]
        for dept_id, name in departments
    ]
    rows.append([InlineKeyboardButton("📋 Barchasi", callback_data="dept:all")])
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def log_pager(page: int, has_next: bool) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"log:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"log:{page + 1}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton("🔄 Yangilash", callback_data=f"log:{page}")])
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def notify_settings(attendance_on: bool, presence_on: bool) -> InlineKeyboardMarkup:
    att_label = "🔔 Davomat xabarlari: YOQILGAN" if attendance_on else "🔕 Davomat xabarlari: O'CHIQ"
    pres_label = "🔔 Harakat xabarlari: YOQILGAN" if presence_on else "🔕 Harakat xabarlari: O'CHIQ"
    rows = [
        [InlineKeyboardButton(att_label, callback_data="notify:att")],
        [InlineKeyboardButton(pres_label, callback_data="notify:presence")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")],
    ]
    return InlineKeyboardMarkup(rows)
