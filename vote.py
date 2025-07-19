import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
import sqlite3
from collections import defaultdict

# تنظیمات اولیه
API_TOKEN = '7525942917:AAFdN_ICJlqNeDdW-w2UT4pvC1GB8NUIOA8'
OWNER_ID = 5910048772
CHANNEL_USERNAME = '@StarCraft_MCC'

bot = telebot.TeleBot(API_TOKEN)

# --- تابع بررسی مالک ---
def is_owner(message):
    return message.from_user.id == OWNER_ID

# --- پایگاه داده ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channel_posts (
        message_id INTEGER PRIMARY KEY,
        text TEXT,
        emoji TEXT,
        vote_count INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_votes (
        user_id INTEGER,
        message_id INTEGER,
        PRIMARY KEY (user_id, message_id)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- توابع کمکی پایگاه داده ---
def save_post(message_id, text, emoji, vote_count=0):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO channel_posts VALUES (?, ?, ?, ?)', 
                 (message_id, text, emoji, vote_count))
    conn.commit()
    conn.close()

def add_vote(user_id, message_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO user_votes VALUES (?, ?)', (user_id, message_id))
        cursor.execute('UPDATE channel_posts SET vote_count = vote_count + 1 WHERE message_id = ?', (message_id,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_vote(user_id, message_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_votes WHERE user_id = ? AND message_id = ?', (user_id, message_id))
    affected = cursor.execute('UPDATE channel_posts SET vote_count = vote_count - 1 WHERE message_id = ?', (message_id,)).rowcount
    conn.commit()
    conn.close()
    return affected > 0

def has_voted(user_id, message_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM user_votes WHERE user_id = ? AND message_id = ?', (user_id, message_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_post_data(message_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT text, emoji, vote_count FROM channel_posts WHERE message_id = ?', (message_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (None, None, 0)

def get_all_posts():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_id, emoji, vote_count FROM channel_posts')
    result = cursor.fetchall()
    conn.close()
    return result

# --- مدیریت حالت‌های کاربر ---
user_state = {}
user_data = {}

def cancel_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ لغو")
    return markup

def main_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("ساخت پست جدید")
    return markup

def edit_options_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("ویرایش متن", "ویرایش اموجی")
    markup.add("❌ لغو")
    return markup

def post_confirmation_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("انتشار در کانال", "ویرایش")
    markup.add("❌ لغو")
    return markup

# --- بازیابی وضعیت پس از راه‌اندازی ---
def restore_voting_buttons():
    posts = get_all_posts()
    for message_id, emoji, vote_count in posts:
        try:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text=f"{emoji} {vote_count}", callback_data="vote"))
            bot.edit_message_reply_markup(
                chat_id=CHANNEL_USERNAME,
                message_id=message_id,
                reply_markup=markup
            )
        except Exception as e:
            print(f"⚠️ خطا در بازیابی دکمه برای پست {message_id}: {e}")

# --- دستورات ربات ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_owner(message):
        return
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda msg: is_owner(msg) and msg.text == "ساخت پست جدید")
def create_new_post(message):
    bot.send_message(message.chat.id, "👋 لطفاً متن پست را وارد کنید:", reply_markup=cancel_keyboard())
    user_state[message.chat.id] = 'awaiting_text'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'awaiting_text')
def get_post_text(message):
    if message.text == "❌ لغو":
        bot.send_message(message.chat.id, "🔙 به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard())
        user_state.pop(message.chat.id, None)
        return
    
    user_data[message.chat.id] = {'text': message.text}
    user_state[message.chat.id] = 'awaiting_emoji'
    bot.send_message(message.chat.id, "👌 حالا یک اموجی بفرست (مثلاً ❤️):", reply_markup=cancel_keyboard())

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'awaiting_emoji')
def get_post_emoji(message):
    if message.text == "❌ لغو":
        bot.send_message(message.chat.id, "🔙 به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard())
        user_state.pop(message.chat.id, None)
        user_data.pop(message.chat.id, None)
        return
    
    emoji = message.text.strip()
    user_data[message.chat.id]['emoji'] = emoji
    text = user_data[message.chat.id]['text']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=f"{emoji} 0", callback_data="vote_temp"))
    
    bot.send_message(message.chat.id, f"🔻 پیش‌نمایش پست:\n\n{text}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ اگر تأیید کردید گزینه مورد نظر را انتخاب کنید:", 
                    reply_markup=post_confirmation_keyboard())
    user_state[message.chat.id] = 'ready_to_post'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'ready_to_post' and msg.text == "ویرایش")
def edit_post(message):
    bot.send_message(message.chat.id, "چه قسمتی را می‌خواهید ویرایش کنید؟", 
                    reply_markup=edit_options_keyboard())
    user_state[message.chat.id] = 'editing_choice'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'editing_choice' and msg.text == "ویرایش متن")
def edit_text(message):
    bot.send_message(message.chat.id, "✏️ متن جدید را وارد کنید:", reply_markup=cancel_keyboard())
    user_state[message.chat.id] = 'editing_text'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'editing_text')
def save_edited_text(message):
    if message.text == "❌ لغو":
        bot.send_message(message.chat.id, "🔙 به مرحله قبل بازگشتید.", reply_markup=post_confirmation_keyboard())
        user_state[message.chat.id] = 'ready_to_post'
        return
    
    user_data[message.chat.id]['text'] = message.text
    emoji = user_data[message.chat.id]['emoji']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=f"{emoji} 0", callback_data="vote_temp"))
    
    bot.send_message(message.chat.id, f"🔻 پیش‌نمایش پست:\n\n{message.text}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ متن با موفقیت ویرایش شد!", 
                    reply_markup=post_confirmation_keyboard())
    user_state[message.chat.id] = 'ready_to_post'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'editing_choice' and msg.text == "ویرایش اموجی")
def edit_emoji(message):
    bot.send_message(message.chat.id, "🎭 اموجی جدید را وارد کنید:", reply_markup=cancel_keyboard())
    user_state[message.chat.id] = 'editing_emoji'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'editing_emoji')
def save_edited_emoji(message):
    if message.text == "❌ لغو":
        bot.send_message(message.chat.id, "🔙 به مرحله قبل بازگشتید.", reply_markup=post_confirmation_keyboard())
        user_state[message.chat.id] = 'ready_to_post'
        return
    
    new_emoji = message.text.strip()
    user_data[message.chat.id]['emoji'] = new_emoji
    text = user_data[message.chat.id]['text']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=f"{new_emoji} 0", callback_data="vote_temp"))
    
    bot.send_message(message.chat.id, f"🔻 پیش‌نمایش پست:\n\n{text}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ اموجی با موفقیت ویرایش شد!", 
                    reply_markup=post_confirmation_keyboard())
    user_state[message.chat.id] = 'ready_to_post'

@bot.message_handler(func=lambda msg: is_owner(msg) and user_state.get(msg.chat.id) == 'ready_to_post' and msg.text == "انتشار در کانال")
def publish_post(message):
    text = user_data[message.chat.id]['text']
    emoji = user_data[message.chat.id]['emoji']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=f"{emoji} 0", callback_data="vote"))
    
    sent = bot.send_message(CHANNEL_USERNAME, text, reply_markup=markup)
    msg_id = sent.message_id
    
    save_post(msg_id, text, emoji)
    
    bot.send_message(message.chat.id, "✅ پست با موفقیت در کانال منتشر شد!", reply_markup=main_menu_keyboard())
    user_state.pop(message.chat.id, None)
    user_data.pop(message.chat.id, None)

@bot.message_handler(func=lambda msg: is_owner(msg) and msg.text == "❌ لغو")
def handle_cancel(message):
    current_state = user_state.get(message.chat.id)
    
    if current_state in ['awaiting_text', 'awaiting_emoji']:
        bot.send_message(message.chat.id, "🔙 به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard())
    elif current_state in ['ready_to_post', 'editing_choice', 'editing_text', 'editing_emoji']:
        bot.send_message(message.chat.id, "🔙 به مرحله قبل بازگشتید.", reply_markup=post_confirmation_keyboard())
    else:
        bot.send_message(message.chat.id, "🔙 به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard())
    
    user_state.pop(message.chat.id, None)
    if current_state not in ['awaiting_text']:
        user_data.pop(message.chat.id, None)

# --- سیستم رأی‌گیری ---
@bot.callback_query_handler(func=lambda call: call.data == 'vote')
def handle_vote(call):
    user_id = call.from_user.id
    message_id = call.message.message_id

    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status not in ['member', 'creator', 'administrator']:
            raise Exception("Not a member")
    except:
        bot.answer_callback_query(call.id, "🔒 برای رأی دادن باید عضو کانال شوید.", show_alert=True)
        return

    text, emoji, vote_count = get_post_data(message_id)
    
    if has_voted(user_id, message_id):
        if remove_vote(user_id, message_id):
            bot.answer_callback_query(call.id, "❌ شما رأی خود را پس گرفتید.")
        else:
            bot.answer_callback_query(call.id, "⚠️ خطا در پس گرفتن رأی!")
    else:
        if add_vote(user_id, message_id):
            bot.answer_callback_query(call.id, "✅ شما به این پست رأی دادید.")
        else:
            bot.answer_callback_query(call.id, "⚠️ شما قبلاً به این پست رأی داده‌اید!")

    new_vote_count = get_post_data(message_id)[2]
    new_markup = InlineKeyboardMarkup()
    new_markup.add(InlineKeyboardButton(text=f"{emoji} {new_vote_count}", callback_data="vote"))
    
    try:
        bot.edit_message_reply_markup(
            chat_id=CHANNEL_USERNAME,
            message_id=message_id,
            reply_markup=new_markup
        )
    except Exception as e:
        print(f"⚠️ خطا در ویرایش دکمه: {e}")

# --- اجرای ربات ---
if __name__ == "__main__":
    print("🤖 ربات در حال راه‌اندازی...")
    restore_voting_buttons()
    print("✅ بازیابی داده‌های قبلی انجام شد.")
    bot.infinity_polling()
