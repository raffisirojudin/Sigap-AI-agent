"""
Sigap - AI Agent dengan Tools
Streamlit app: AI yang bisa "bertindak" -- bukan cuma ngomong -- dengan
memanggil tools nyata (cuaca, kalkulator, waktu, kurs) lewat function calling
Gemini API. Semua tools memakai layanan gratis tanpa API key tambahan.
"""

import ast
import operator
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from google import genai
from google.genai import types

# ============================================================
# KONFIGURASI HALAMAN & KONSTANTA
# ============================================================
st.set_page_config(page_title="Sigap", page_icon="🛠️", layout="centered")

APP_VERSION = "v1.0"
MODEL_NAME = "gemini-2.5-flash-lite"


# ============================================================
# SECRETS
# ============================================================
def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
APP_PASSWORD = get_secret("APP_PASSWORD")

if not GEMINI_API_KEY:
    st.title("🛠️ Sigap")
    st.error("⚠️ Setup belum lengkap. Tambahkan secret berikut dulu:")
    st.code('GEMINI_API_KEY = "key-gemini-kamu"', language="toml")
    st.caption("Isi lewat Settings → Secrets (Streamlit Cloud) atau .streamlit/secrets.toml (lokal).")
    st.stop()


# ============================================================
# PROTEKSI PASSWORD (opsional)
# ============================================================
if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🛠️ Sigap")
        st.caption("🔒 Aplikasi ini dilindungi password.")
        pwd_input = st.text_input("Masukkan password", type="password", key="app_password_gate")
        if st.button("Masuk", type="primary"):
            if pwd_input == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password salah, coba lagi.")
        st.stop()


# ============================================================
# TOOLS -- fungsi nyata yang bisa "dipanggil" oleh AI
# Docstring & type hint di bawah dipakai Gemini buat tahu kapan dan
# bagaimana cara memanggil tiap fungsi (otomatis, lewat Automatic
# Function Calling / AFC dari SDK google-genai).
# ============================================================

def get_weather(city: str) -> str:
    """Mendapatkan informasi cuaca terkini untuk sebuah kota di dunia.

    Args:
        city: Nama kota, misalnya 'Jakarta', 'Bandung', atau 'Tokyo'.
    """
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "id"},
            timeout=15,
        ).json()
        if not geo.get("results"):
            return f"Kota '{city}' tidak ditemukan."
        loc = geo["results"][0]
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": loc["latitude"], "longitude": loc["longitude"], "current_weather": "true"},
            timeout=15,
        ).json()
        cw = weather.get("current_weather", {})
        return (
            f"Cuaca di {loc['name']}, {loc.get('country', '')}: "
            f"suhu {cw.get('temperature')}°C, kecepatan angin {cw.get('windspeed')} km/jam."
        )
    except Exception as e:
        return f"Gagal mengambil data cuaca: {e}"


_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Ekspresi tidak didukung -- hanya angka dan operator dasar (+ - * / ** %).")


def calculate(expression: str) -> str:
    """Menghitung sebuah ekspresi matematika dengan aman.

    Args:
        expression: Ekspresi matematika, misalnya '12 * (3 + 4)' atau '2 ** 10'.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return f"Hasil dari '{expression}' adalah {result}."
    except Exception as e:
        return f"Gagal menghitung ekspresi '{expression}': {e}"


def get_current_time(timezone: str = "Asia/Jakarta") -> str:
    """Mendapatkan tanggal dan waktu saat ini di suatu zona waktu (IANA timezone).

    Args:
        timezone: Nama zona waktu, misalnya 'Asia/Jakarta', 'Asia/Tokyo', 'America/New_York', 'Europe/London'.
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
        return f"Waktu saat ini di {timezone}: {now.strftime('%A, %d %B %Y, %H:%M:%S')}."
    except Exception as e:
        return f"Zona waktu '{timezone}' tidak dikenali: {e}"


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Mengonversi nilai uang dari satu mata uang ke mata uang lain memakai kurs terkini.

    Args:
        amount: Jumlah uang yang ingin dikonversi.
        from_currency: Kode mata uang asal (3 huruf), misalnya 'USD', 'IDR', 'EUR', 'JPY'.
        to_currency: Kode mata uang tujuan (3 huruf), misalnya 'IDR', 'USD', 'SGD'.
    """
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"amount": amount, "from": from_currency.upper(), "to": to_currency.upper()},
            timeout=15,
        ).json()
        rate_value = resp["rates"][to_currency.upper()]
        return f"{amount:,.2f} {from_currency.upper()} = {rate_value:,.2f} {to_currency.upper()}."
    except Exception as e:
        return f"Gagal mengonversi mata uang: {e}"


_UNIT_CONVERSIONS = {
    ("km", "mil"): lambda v: v * 0.621371,
    ("mil", "km"): lambda v: v / 0.621371,
    ("kg", "lbs"): lambda v: v * 2.20462,
    ("lbs", "kg"): lambda v: v / 2.20462,
    ("celsius", "fahrenheit"): lambda v: v * 9 / 5 + 32,
    ("fahrenheit", "celsius"): lambda v: (v - 32) * 5 / 9,
    ("m", "ft"): lambda v: v * 3.28084,
    ("ft", "m"): lambda v: v / 3.28084,
    ("cm", "inch"): lambda v: v / 2.54,
    ("inch", "cm"): lambda v: v * 2.54,
}


def convert_unit(value: float, from_unit: str, to_unit: str) -> str:
    """Mengonversi nilai satuan pengukuran umum: panjang, berat, dan suhu.

    Args:
        value: Nilai yang ingin dikonversi.
        from_unit: Satuan asal. Pilihan: 'km', 'mil', 'kg', 'lbs', 'celsius', 'fahrenheit', 'm', 'ft', 'cm', 'inch'.
        to_unit: Satuan tujuan, dari daftar yang sama dengan from_unit.
    """
    key = (from_unit.lower().strip(), to_unit.lower().strip())
    if key not in _UNIT_CONVERSIONS:
        return f"Konversi dari '{from_unit}' ke '{to_unit}' belum didukung."
    result = _UNIT_CONVERSIONS[key](value)
    return f"{value} {from_unit} = {result:.4g} {to_unit}."


def roll_dice(sides: int = 6, count: int = 1) -> str:
    """Melempar dadu virtual secara acak.

    Args:
        sides: Jumlah sisi dadu, misalnya 6 untuk dadu standar atau 20 untuk dadu D&D.
        count: Berapa kali dadu dilempar sekaligus.
    """
    if sides < 2 or count < 1 or count > 20:
        return "Jumlah sisi minimal 2, dan jumlah lemparan maksimal 20 sekali jalan."
    results = [random.randint(1, sides) for _ in range(count)]
    return f"Hasil lempar {count}x dadu {sides} sisi: {results} (total: {sum(results)})."


_RANDOM_FACTS = [
    "Madu nggak akan pernah basi kalau disimpan dengan benar -- arkeolog pernah menemukan madu berusia 3000 tahun yang masih bisa dimakan.",
    "Jantung udang ada di kepalanya.",
    "Satu hari di planet Venus lebih lama daripada satu tahun di Venus.",
    "Bintang laut nggak punya otak.",
    "Gurita punya 3 jantung dan darah berwarna biru.",
    "Komodo, kadal terbesar di dunia, cuma ditemukan secara alami di Indonesia.",
    "Air mendidih lebih cepat di puncak gunung dibanding di permukaan laut.",
    "Bahasa Indonesia dipakai sebagai bahasa kedua oleh ratusan juta orang di Asia Tenggara.",
]


def random_fact() -> str:
    """Memberikan satu fakta menarik dan acak tentang dunia."""
    return random.choice(_RANDOM_FACTS)


AVAILABLE_TOOLS = [get_weather, calculate, get_current_time, convert_currency, convert_unit, roll_dice, random_fact]


# ============================================================
# HELPER: GEMINI + FUNCTION CALLING
# ============================================================
def handle_gemini_error(e):
    msg = str(e).lower()
    if "resource_exhausted" in msg or "429" in msg or "quota" in msg:
        st.error("⏳ Kuota Gemini habis untuk saat ini. Coba lagi beberapa saat lagi.")
    elif "unavailable" in msg or "503" in msg:
        st.error("🔄 Server Gemini sedang sibuk. Coba lagi sebentar.")
    elif "api_key_invalid" in msg or "401" in msg or "403" in msg:
        st.error("🔑 API Key Gemini tidak valid. Cek lagi di Secrets.")
    else:
        st.error(f"Terjadi kesalahan: {e}")


def build_contents(chat_history, new_message):
    contents = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])])
        for m in chat_history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=new_message)]))
    return contents


def extract_tool_calls(afc_history):
    """Pasangkan setiap function_call dengan function_response dari riwayat AFC."""
    calls = []
    if not afc_history:
        return calls
    for content in afc_history:
        for part in content.parts:
            if getattr(part, "function_call", None):
                calls.append({
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args) if part.function_call.args else {},
                    "result": None,
                })
            elif getattr(part, "function_response", None):
                for c in reversed(calls):
                    if c["name"] == part.function_response.name and c["result"] is None:
                        c["result"] = part.function_response.response
                        break
    return calls


def safe_response_text(response, tool_calls):
    """Ekstrak teks jawaban dengan aman -- response.text bisa None walau tool berhasil dipanggil."""
    text = getattr(response, "text", None)
    if text:
        return text

    # Coba kumpulkan manual dari semua part teks yang ada
    try:
        parts = response.candidates[0].content.parts
        manual_text = "".join(p.text for p in parts if getattr(p, "text", None))
        if manual_text.strip():
            return manual_text
    except Exception:
        pass

    # Fallback terakhir -- jangan biarkan None ikut tersimpan ke riwayat chat
    if tool_calls:
        return (
            "Tool-nya berhasil dipanggil dan hasilnya ada di atas, tapi aku nggak berhasil "
            "menyusun kalimat jawabannya. Coba tanya ulang dengan kalimat yang sedikit berbeda?"
        )
    return "Maaf, aku nggak berhasil menjawab pertanyaan itu. Coba tanya dengan cara lain?"


def call_agent(chat_history, new_message):
    client = genai.Client(api_key=GEMINI_API_KEY)
    contents = build_contents(chat_history, new_message)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(tools=AVAILABLE_TOOLS, temperature=0.3),
    )
    tool_calls = extract_tool_calls(response.automatic_function_calling_history)
    reply_text = safe_response_text(response, tool_calls)
    return reply_text, tool_calls


# ============================================================
# HEADER
# ============================================================
st.title("🛠️ Sigap")
st.caption("AI yang bisa bertindak, bukan cuma ngomong -- ditenagai function calling Gemini.")

badge_col1, badge_col2, badge_col3 = st.columns(3)
with badge_col1:
    st.badge(f"{len(AVAILABLE_TOOLS)} Tools", icon="🛠️", color="blue")
with badge_col2:
    st.badge("Gemini API", icon="✨", color="violet")
with badge_col3:
    st.badge(APP_VERSION, icon="🚀", color="gray")

st.divider()


# ============================================================
# SESSION STATE
# ============================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "tool_log" not in st.session_state:
    st.session_state.tool_log = {}


def reset_all():
    st.session_state.chat_history = []
    st.session_state.tool_log = {}


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### 🛠️ Sigap")
    st.caption("AI Agent dengan Tools")
    st.divider()

    st.header("🧰 Tools yang tersedia")
    st.caption("🌤️ **Cuaca** -- cek cuaca kota apa saja")
    st.caption("🧮 **Kalkulator** -- hitung ekspresi matematika")
    st.caption("🕐 **Waktu** -- cek waktu di zona waktu manapun")
    st.caption("💱 **Kurs** -- konversi mata uang terkini")
    st.caption("📏 **Satuan** -- konversi panjang/berat/suhu")
    st.caption("🎲 **Dadu** -- lempar dadu virtual")
    st.caption("🎯 **Fakta Acak** -- fakta menarik random")
    st.caption("AI sendiri yang memutuskan tool mana yang dipanggil, berdasarkan pertanyaanmu.")

    st.divider()
    st.button("🧹 Mulai Obrolan Baru", on_click=reset_all, use_container_width=True)

    st.divider()
    st.header("🧪 Tes Tools Manual")
    st.caption("Coba tiap tool langsung, tanpa lewat AI -- buat lihat fungsi mentahnya kerja gimana.")

    with st.expander("🌤️ Cuaca"):
        t_city = st.text_input("Kota", value="Jakarta", key="t_city")
        if st.button("Jalankan", key="run_weather", use_container_width=True):
            st.info(get_weather(t_city))

    with st.expander("🧮 Kalkulator"):
        t_expr = st.text_input("Ekspresi", value="12 * (3 + 4)", key="t_expr")
        if st.button("Jalankan", key="run_calc", use_container_width=True):
            st.info(calculate(t_expr))

    with st.expander("🕐 Waktu"):
        t_tz = st.text_input("Zona waktu (IANA)", value="Asia/Jakarta", key="t_tz")
        if st.button("Jalankan", key="run_time", use_container_width=True):
            st.info(get_current_time(t_tz))

    with st.expander("💱 Kurs"):
        t_amount = st.number_input("Jumlah", value=100.0, key="t_amount")
        t_from = st.text_input("Dari", value="USD", key="t_from")
        t_to = st.text_input("Ke", value="IDR", key="t_to")
        if st.button("Jalankan", key="run_currency", use_container_width=True):
            st.info(convert_currency(t_amount, t_from, t_to))

    with st.expander("📏 Satuan"):
        t_value = st.number_input("Nilai", value=10.0, key="t_value")
        t_unit_from = st.text_input("Dari satuan", value="km", key="t_unit_from")
        t_unit_to = st.text_input("Ke satuan", value="mil", key="t_unit_to")
        if st.button("Jalankan", key="run_unit", use_container_width=True):
            st.info(convert_unit(t_value, t_unit_from, t_unit_to))

    with st.expander("🎲 Dadu"):
        t_sides = st.number_input("Sisi dadu", value=6, min_value=2, key="t_sides")
        t_count = st.number_input("Jumlah lemparan", value=1, min_value=1, max_value=20, key="t_count")
        if st.button("Jalankan", key="run_dice", use_container_width=True):
            st.info(roll_dice(int(t_sides), int(t_count)))

    with st.expander("🎯 Fakta Acak"):
        if st.button("Jalankan", key="run_fact", use_container_width=True):
            st.info(random_fact())


# ============================================================
# AREA CHAT UTAMA
# ============================================================
for i, msg in enumerate(st.session_state.chat_history):
    role = "user" if msg["role"] == "user" else "assistant"
    with st.chat_message(role):
        st.write(msg["content"])
        if i in st.session_state.tool_log:
            with st.expander("🔧 Tools yang dipanggil"):
                for call in st.session_state.tool_log[i]:
                    st.markdown(f"**`{call['name']}`**({', '.join(f'{k}={v!r}' for k, v in call['args'].items())})")
                    st.caption(f"↳ {call['result']}")

if not st.session_state.chat_history:
    st.caption("💡 Coba tanya:")
    suggested_questions = [
        "Cuaca di Jakarta gimana?",
        "100 USD ke IDR berapa?",
        "Lempar dadu 2 kali",
        "Kasih aku fakta acak",
    ]
    chip_cols = st.columns(len(suggested_questions))
    for col, q in zip(chip_cols, suggested_questions):
        with col:
            if st.button(q, key=f"suggest_{q}", use_container_width=True):
                st.session_state.pending_message = q

new_message = st.chat_input("Tanya apa saja -- cuaca, hitung-hitungan, jam, kurs, satuan, dadu, atau fakta acak...")
effective_message = new_message or st.session_state.pop("pending_message", None)

if effective_message:
    st.session_state.chat_history.append({"role": "user", "content": effective_message})
    with st.chat_message("user"):
        st.write(effective_message)

    try:
        with st.chat_message("assistant"):
            with st.spinner("Sigap berpikir..."):
                reply, tool_calls = call_agent(st.session_state.chat_history[:-1], effective_message)
            st.write(reply)
            if tool_calls:
                with st.expander("🔧 Tools yang dipanggil"):
                    for call in tool_calls:
                        st.markdown(f"**`{call['name']}`**({', '.join(f'{k}={v!r}' for k, v in call['args'].items())})")
                        st.caption(f"↳ {call['result']}")

        msg_index = len(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "model", "content": reply or "(tidak ada jawaban)"})
        if tool_calls:
            st.session_state.tool_log[msg_index] = tool_calls
    except Exception as e:
        handle_gemini_error(e)


# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(f"🛠️ Sigap {APP_VERSION} · Ditenagai Gemini Function Calling · Proyek pembelajaran AI API")
