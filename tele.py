import base64
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
BOT_TOKEN        = "8558932982:AAHi_IQcfM3eKQSEtQU2Dj0yg2V5fakDViA"
URL_GITHUB_TOKEN = "https://pastebin.com/raw/Kips1n58"
GITHUB_OWNER     = "yutywood"
GITHUB_REPO      = "akses"
GITHUB_BRANCH    = "main"
GITHUB_FILE_PATH = "JanganDiDecDong.txt"

ADMIN_IDS = {7316824198}

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

H = "HTML"  # shorthand parse_mode

# ─────────────────────────────────────────
# ADMIN GUARD
# ─────────────────────────────────────────
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in ADMIN_IDS

async def deny(update: Update):
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.full_name
    await update.message.reply_text(
        f"🚫 <b>Akses Ditolak!</b>\n\n"
        f"Hanya Admin, kamu siapa?\n"
        f"Kamu itu cuma Kroco ! {name} (<code>{user.id}</code>)",
        parse_mode=H
    )

# ─────────────────────────────────────────
# GITHUB HELPERS
# ─────────────────────────────────────────
def fetch_github_token() -> str:
    try:
        r = requests.get(URL_GITHUB_TOKEN, timeout=10)
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        logger.error(f"Gagal ambil GitHub token: {e}")
        return ""

def github_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def get_file_content_and_sha(token: str):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=github_headers(token), timeout=10)
    if r.status_code == 200:
        data    = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha     = data["sha"]
        return content, sha
    return None, None

def push_file_content(token: str, content: str, sha: str, commit_msg: str) -> dict:
    url     = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    encoded = base64.b64encode(content.encode("utf-8")).decode()
    payload = {
        "message": commit_msg,
        "content": encoded,
        "sha":     sha,
        "branch":  GITHUB_BRANCH
    }
    r = requests.put(url, headers=github_headers(token), json=payload, timeout=15)
    return {"status": r.status_code, "json": r.json()}

def push_arbitrary_file(token: str, owner: str, repo: str, branch: str,
                         file_path: str, raw_bytes: bytes, commit_msg: str) -> dict:
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    r_check = requests.get(f"{api_url}?ref={branch}", headers=github_headers(token), timeout=10)
    sha = r_check.json().get("sha") if r_check.status_code == 200 else None
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(raw_bytes).decode(),
        "branch":  branch
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(api_url, headers=github_headers(token), json=payload, timeout=20)
    return {"status": r.status_code, "json": r.json()}

def parse_github_repo_link(link: str):
    link = link.strip().rstrip("/")
    owner, repo, branch, folder = None, None, "main", ""
    if "github.com" in link:
        link = link.split("github.com/", 1)[-1]
    parts = link.split("/")
    if len(parts) >= 2:
        owner = parts[0]
        repo  = parts[1].replace(".git", "")
    if len(parts) >= 4 and parts[2] == "tree":
        branch = parts[3]
        folder = "/".join(parts[4:]) if len(parts) > 4 else ""
    return owner, repo, branch, folder

def key_exists(content: str, key: str) -> bool:
    return key.strip() in [line.strip() for line in content.splitlines() if line.strip()]

def add_key_to_content(content: str, key: str) -> str:
    if content and not content.endswith("\n"):
        content += "\n"
    return content + key.strip() + "\n"

def remove_key_from_content(content: str, key: str) -> str:
    lines = [line for line in content.splitlines() if line.strip() != key.strip()]
    return "\n".join(lines) + ("\n" if lines else "")

def list_keys(content: str) -> list:
    return [line.strip() for line in content.splitlines() if line.strip()]

# ─────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Key",     callback_data="guide_add")],
        [InlineKeyboardButton("❌ Remove Key",  callback_data="guide_remove")],
        [InlineKeyboardButton("🗑 Remove All",  callback_data="confirm_removeall")],
        [InlineKeyboardButton("📋 List Keys",   callback_data="list_keys")],
        [InlineKeyboardButton("🔍 Cek Key",     callback_data="guide_check")],
    ]
    await update.message.reply_text(
        "<b>🔑 GitHub Key Manager Bot</b>\n\n"
        "Bot untuk manage whitelist key di GitHub.\n\n"
        "<b>Commands:</b>\n"
        "<code>/add KEY</code> — Tambah key ke whitelist\n"
        "<code>/remove KEY</code> — Hapus key dari whitelist\n"
        "<code>/removeall</code> — Hapus SEMUA key\n"
        "<code>/list</code> — Lihat semua key\n"
        "<code>/check KEY</code> — Cek apakah key ada\n"
        "<code>/addfile REPO</code> — Push file ke repo GitHub\n\n"
        "Kirim file ke bot dulu, lalu /addfile repo\n\n"
        "Atau gunakan tombol di bawah:",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Format: <code>/add KEY</code>\n"
            "Contoh: <code>/add STX-ABCDEF123-xyz123</code>",
            parse_mode=H
        )
        return

    key = " ".join(context.args).strip()
    msg = await update.message.reply_text(f"⏳ Menambahkan key <code>{key}</code>...", parse_mode=H)

    token = fetch_github_token()
    if not token:
        await msg.edit_text("❌ Gagal mengambil GitHub token.")
        return

    content, sha = get_file_content_and_sha(token)
    if content is None:
        await msg.edit_text("❌ Gagal membaca file whitelist dari GitHub.")
        return

    if key_exists(content, key):
        await msg.edit_text(f"⚠️ Key <code>{key}</code> sudah ada di whitelist.", parse_mode=H)
        return

    new_content = add_key_to_content(content, key)
    result = push_file_content(token, new_content, sha, f"Add key: {key}")

    if result["status"] in (200, 201):
        commit_url = result["json"].get("commit", {}).get("html_url", "")
        total = len(list_keys(new_content))
        text = (
            f"✅ <b>Key berhasil ditambahkan!</b>\n\n"
            f"🔑 Key: <code>{key}</code>\n"
            f"📊 Total key: <code>{total}</code>"
        )
        if commit_url:
            text += f'\n🔗 <a href="{commit_url}">Lihat Commit</a>'
        await msg.edit_text(text, parse_mode=H)
    else:
        err = result["json"].get("message", "Unknown error")
        await msg.edit_text(f"❌ Gagal push!\nError: <code>{err}</code>", parse_mode=H)

async def remove_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Format: <code>/remove KEY</code>\n"
            "Contoh: <code>/remove STX-ABCDEF123-xyz123</code>",
            parse_mode=H
        )
        return

    key = " ".join(context.args).strip()
    msg = await update.message.reply_text(f"⏳ Menghapus key <code>{key}</code>...", parse_mode=H)

    token = fetch_github_token()
    if not token:
        await msg.edit_text("❌ Gagal mengambil GitHub token.")
        return

    content, sha = get_file_content_and_sha(token)
    if content is None:
        await msg.edit_text("❌ Gagal membaca file whitelist dari GitHub.")
        return

    if not key_exists(content, key):
        await msg.edit_text(f"⚠️ Key <code>{key}</code> tidak ditemukan di whitelist.", parse_mode=H)
        return

    new_content = remove_key_from_content(content, key)
    result = push_file_content(token, new_content, sha, f"Remove key: {key}")

    if result["status"] in (200, 201):
        total = len(list_keys(new_content))
        await msg.edit_text(
            f"✅ <b>Key berhasil dihapus!</b>\n\n"
            f"🔑 Key: <code>{key}</code>\n"
            f"📊 Sisa key: <code>{total}</code>",
            parse_mode=H
        )
    else:
        err = result["json"].get("message", "Unknown error")
        await msg.edit_text(f"❌ Gagal push!\nError: <code>{err}</code>", parse_mode=H)

async def remove_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    keyboard = [[
        InlineKeyboardButton("✅ YA, Hapus Semua!", callback_data="do_removeall"),
        InlineKeyboardButton("❌ Batal",            callback_data="cancel_removeall"),
    ]]
    await update.message.reply_text(
        "⚠️ <b>PERINGATAN!</b>\n\n"
        "Kamu akan menghapus <b>SEMUA KEY</b> dari whitelist GitHub.\n\n"
        "Aksi ini tidak bisa dibatalkan! Yakin?",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def list_keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    msg = await update.message.reply_text("⏳ Mengambil daftar key...")

    token = fetch_github_token()
    if not token:
        await msg.edit_text("❌ Gagal mengambil GitHub token.")
        return

    content, _ = get_file_content_and_sha(token)
    if content is None:
        await msg.edit_text("❌ Gagal membaca file whitelist dari GitHub.")
        return

    keys = list_keys(content)
    if not keys:
        await msg.edit_text("📋 Whitelist kosong. Belum ada key terdaftar.")
        return

    display  = keys[:50]
    key_list = "\n".join(f"<code>{i+1}. {k}</code>" for i, k in enumerate(display))
    footer   = f"\n\n(...dan {len(keys)-50} key lainnya)" if len(keys) > 50 else ""

    await msg.edit_text(
        f"📋 <b>Whitelist Key ({len(keys)} total):</b>\n\n{key_list}{footer}",
        parse_mode=H
    )

async def check_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    if not context.args:
        await update.message.reply_text("⚠️ Format: <code>/check KEY</code>", parse_mode=H)
        return

    key = " ".join(context.args).strip()
    msg = await update.message.reply_text(f"🔍 Mengecek key <code>{key}</code>...", parse_mode=H)

    token      = fetch_github_token()
    content, _ = get_file_content_and_sha(token)
    if content is None:
        await msg.edit_text("❌ Gagal membaca file whitelist.")
        return

    if key_exists(content, key):
        await msg.edit_text(f"✅ Key <code>{key}</code> <b>ADA</b> di whitelist.", parse_mode=H)
    else:
        await msg.edit_text(f"❌ Key <code>{key}</code> <b>TIDAK ADA</b> di whitelist.", parse_mode=H)

async def addfile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    pending = context.user_data.get("pending_file")
    if not pending:
        await update.message.reply_text(
            "⚠️ <b>Belum ada file yang dikirim!</b>\n\n"
            "Kirim dulu file ke bot, lalu gunakan:\n"
            "<code>/addfile https://github.com/owner/repo</code>\n\n"
            "Contoh dengan folder:\n"
            "<code>/addfile https://github.com/yutywood/akses/tree/main/scripts</code>",
            parse_mode=H
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Format: <code>/addfile REPO_LINK</code>\n\n"
            "Contoh:\n"
            "<code>/addfile https://github.com/yutywood/akses</code>\n"
            "<code>/addfile https://github.com/yutywood/akses/tree/main/folder</code>",
            parse_mode=H
        )
        return

    repo_link = context.args[0].strip()
    owner, repo, branch, folder = parse_github_repo_link(repo_link)

    if not owner or not repo:
        await update.message.reply_text(
            "❌ Link repo tidak valid.\n"
            "Contoh: <code>https://github.com/username/reponame</code>",
            parse_mode=H
        )
        return

    file_name  = pending["name"]
    file_bytes = pending["bytes"]
    file_path  = f"{folder}/{file_name}".lstrip("/") if folder else file_name

    msg = await update.message.reply_text(
        f"⏳ Mempush file ke GitHub...\n\n"
        f"📄 File: <code>{file_name}</code>\n"
        f"📁 Repo: <code>{owner}/{repo}</code>\n"
        f"🌿 Branch: <code>{branch}</code>\n"
        f"📂 Path: <code>{file_path}</code>",
        parse_mode=H
    )

    token = fetch_github_token()
    if not token:
        await msg.edit_text("❌ Gagal mengambil GitHub token.")
        return

    result = push_arbitrary_file(
        token=token, owner=owner, repo=repo, branch=branch,
        file_path=file_path, raw_bytes=file_bytes,
        commit_msg=f"Bot upload: {file_name}"
    )

    if result["status"] in (200, 201):
        commit_url = result["json"].get("commit", {}).get("html_url", "")
        raw_url    = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        action     = "diperbarui" if result["status"] == 200 else "ditambahkan"
        text = (
            f"✅ <b>File berhasil {action}!</b>\n\n"
            f"📄 Nama: <code>{file_name}</code>\n"
            f"📁 Repo: <code>{owner}/{repo}</code>\n"
            f"🌿 Branch: <code>{branch}</code>\n"
            f"📂 Path: <code>{file_path}</code>\n"
            f'🔗 Raw: <a href="{raw_url}">Lihat File</a>'
        )
        if commit_url:
            text += f'\n📝 <a href="{commit_url}">Lihat Commit</a>'
        await msg.edit_text(text, parse_mode=H)
        context.user_data.pop("pending_file", None)
    else:
        err = result["json"].get("message", "Unknown error")
        await msg.edit_text(f"❌ <b>Gagal push file!</b>\n\nError: <code>{err}</code>", parse_mode=H)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    doc       = update.message.document
    file_name = doc.file_name or "file_tanpa_nama"
    file_size = doc.file_size or 0

    tg_file   = await context.bot.get_file(doc.file_id)
    raw_bytes = await tg_file.download_as_bytearray()

    context.user_data["pending_file"] = {
        "name":  file_name,
        "bytes": bytes(raw_bytes),
        "size":  file_size,
    }

    size_kb = round(file_size / 1024, 2)
    await update.message.reply_text(
        f"📁 <b>File terdeteksi!</b>\n\n"
        f"📄 Nama: <code>{file_name}</code>\n"
        f"📦 Ukuran: <code>{size_kb} KB</code>\n\n"
        f"Sekarang gunakan perintah:\n"
        f"<code>/addfile https://github.com/owner/repo</code>\n\n"
        f"Contoh dengan folder:\n"
        f"<code>/addfile https://github.com/yutywood/akses/tree/main/scripts</code>",
        parse_mode=H
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = update.message.text.strip()
    if text.startswith("STX-") and len(text) > 10:
        keyboard = [[
            InlineKeyboardButton("➕ Add Key Ini", callback_data=f"add|{text}"),
            InlineKeyboardButton("🔍 Cek Key Ini", callback_data=f"check|{text}"),
        ]]
        await update.message.reply_text(
            f"🔑 Key terdeteksi:\n<code>{text}</code>\n\nMau apa?",
            parse_mode=H,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ─────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.message.reply_text("🚫 <b>Akses Ditolak!</b> Hanya Admin.", parse_mode=H)
        return

    data = query.data

    if data == "guide_add":
        await query.message.reply_text("Gunakan perintah:\n<code>/add KEY</code>", parse_mode=H)

    elif data == "guide_remove":
        await query.message.reply_text("Gunakan perintah:\n<code>/remove KEY</code>", parse_mode=H)

    elif data == "guide_check":
        await query.message.reply_text("Gunakan perintah:\n<code>/check KEY</code>", parse_mode=H)

    elif data == "list_keys":
        msg        = await query.message.reply_text("⏳ Mengambil daftar key...")
        token      = fetch_github_token()
        content, _ = get_file_content_and_sha(token)
        if content is None:
            await msg.edit_text("❌ Gagal membaca file whitelist.")
            return
        keys = list_keys(content)
        if not keys:
            await msg.edit_text("📋 Whitelist kosong.")
            return
        display  = keys[:50]
        key_list = "\n".join(f"<code>{i+1}. {k}</code>" for i, k in enumerate(display))
        footer   = f"\n\n(...dan {len(keys)-50} key lainnya)" if len(keys) > 50 else ""
        await msg.edit_text(
            f"📋 <b>Whitelist Key ({len(keys)} total):</b>\n\n{key_list}{footer}",
            parse_mode=H
        )

    elif data == "confirm_removeall":
        keyboard = [[
            InlineKeyboardButton("✅ YA, Hapus Semua!", callback_data="do_removeall"),
            InlineKeyboardButton("❌ Batal",            callback_data="cancel_removeall"),
        ]]
        await query.message.reply_text(
            "⚠️ <b>PERINGATAN!</b>\n\n"
            "Kamu akan menghapus <b>SEMUA KEY</b> dari whitelist GitHub.\n\n"
            "Aksi ini tidak bisa dibatalkan! Yakin?",
            parse_mode=H,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "cancel_removeall":
        await query.message.edit_text("✅ Dibatalkan. Semua key aman.")

    elif data == "do_removeall":
        await query.message.edit_text("⏳ Menghapus semua key...")
        token = fetch_github_token()
        if not token:
            await query.message.edit_text("❌ Gagal mengambil GitHub token.")
            return
        content, sha = get_file_content_and_sha(token)
        if content is None:
            await query.message.edit_text("❌ Gagal membaca file whitelist.")
            return
        total_before = len(list_keys(content))
        result = push_file_content(token, "", sha, "Remove ALL keys")
        if result["status"] in (200, 201):
            commit_url = result["json"].get("commit", {}).get("html_url", "")
            text = (
                f"🗑 <b>Semua key berhasil dihapus!</b>\n\n"
                f"📊 Total terhapus: <code>{total_before}</code> key\n"
                f"📄 File <code>{GITHUB_FILE_PATH}</code> sekarang kosong."
            )
            if commit_url:
                text += f'\n🔗 <a href="{commit_url}">Lihat Commit</a>'
            await query.message.edit_text(text, parse_mode=H)
        else:
            err = result["json"].get("message", "Unknown error")
            await query.message.edit_text(f"❌ Gagal!\nError: <code>{err}</code>", parse_mode=H)

    elif data.startswith("add|"):
        key          = data[4:]
        msg          = await query.message.reply_text(f"⏳ Menambahkan key <code>{key}</code>...", parse_mode=H)
        token        = fetch_github_token()
        content, sha = get_file_content_and_sha(token)
        if content is None:
            await msg.edit_text("❌ Gagal membaca file whitelist.")
            return
        if key_exists(content, key):
            await msg.edit_text(f"⚠️ Key <code>{key}</code> sudah ada.", parse_mode=H)
            return
        new_content = add_key_to_content(content, key)
        result = push_file_content(token, new_content, sha, f"Add key: {key}")
        if result["status"] in (200, 201):
            await msg.edit_text(f"✅ Key <code>{key}</code> berhasil ditambahkan!", parse_mode=H)
        else:
            await msg.edit_text(f"❌ Gagal: <code>{result['json'].get('message')}</code>", parse_mode=H)

    elif data.startswith("check|"):
        key        = data[6:]
        token      = fetch_github_token()
        content, _ = get_file_content_and_sha(token)
        if content and key_exists(content, key):
            await query.message.reply_text(f"✅ Key <code>{key}</code> ADA di whitelist.", parse_mode=H)
        else:
            await query.message.reply_text(f"❌ Key <code>{key}</code> TIDAK ADA di whitelist.", parse_mode=H)

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    print("🔑 GitHub Key Manager Bot starting...")
    print(f"👑 Admin ID: {ADMIN_IDS}")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("add",       add_key))
    app.add_handler(CommandHandler("remove",    remove_key))
    app.add_handler(CommandHandler("removeall", remove_all))
    app.add_handler(CommandHandler("list",      list_keys_command))
    app.add_handler(CommandHandler("check",     check_key))
    app.add_handler(CommandHandler("addfile",   addfile_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot running! Tekan Ctrl+C untuk stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
