import logging
import sqlite3
import random
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8560892163:AAED-cMa5Nssw4AIoKy-OvrEOJy48emA5R8")

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('/data/casino_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1000,
            last_bonus TIMESTAMP,
            message_count INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blackjack_games (
            user_id INTEGER PRIMARY KEY,
            deck TEXT,
            player_hand TEXT,
            dealer_hand TEXT,
            bet INTEGER
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# Списки слов и реакций
BAD_WORDS = ['мат1', 'мат2', 'плохое_слово']  # Замените на свои

SPECIAL_REACTIONS = {
    'шут': ['Парашют!', 'Глеб!', 'Самолет!'],
    '4:20': ['Курить!', 'Взрывай!', 'Взрывай чувак!'],
    'иван': ['Быстров!', 'Иваныч!', 'Ваня!'],
    'привет': ['И тебе привет!', 'Здарова!', 'Приветствую!'],
    'бот': ['Я здесь!', 'На связи!', 'Чем могу помочь?']
}

TIME_MESSAGES = [
    "Время взрывать!",
    "Пора взрывать!", 
    "Time for smoking!",
    "4:20!",
    "Взрывай!!!",
    "Курим чуваки!",
    "Поджигаем косого!"
]

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 1000)',
        (user_id, username)
    )
    db.commit()
    
    await update.message.reply_text(
        f"🎰 Привет {username}! Добро пожаловать в казино-бот!\n\n"
        f"💰 Начальный баланс: 1000 монет\n\n"
        f"🎮 Команды:\n"
        f"/slots - Игра в слоты (ставка 50)\n"
        f"/blackjack - Начать игру в блэкджек\n"
        f"/bonus - Получить бонус 500 монет (раз в час)\n"
        f"/balance - Мой баланс\n"
        f"/wheel - Колесо фортуны\n"
        f"/stats - Статистика чата\n"
        f"/all - Тегнуть всех участников"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        await update.message.reply_text(f"💰 Ваш баланс: {result[0]} монет")
    else:
        await update.message.reply_text("❌ Напишите /start")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    
    cursor.execute('SELECT last_bonus, balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Напишите /start")
        return
    
    last_bonus, balance = result
    now = datetime.now()
    
    if last_bonus:
        last_bonus = datetime.strptime(last_bonus, '%Y-%m-%d %H:%M:%S.%f')
        if now - last_bonus < timedelta(hours=1):
            time_left = timedelta(hours=1) - (now - last_bonus)
            minutes = time_left.seconds // 60
            await update.message.reply_text(f"⏳ Бонус будет доступен через {minutes} минут")
            return
    
    new_balance = balance + 500
    cursor.execute(
        'UPDATE users SET balance = ?, last_bonus = ? WHERE user_id = ?',
        (new_balance, now, user_id)
    )
    db.commit()
    
    await update.message.reply_text(f"🎁 +500 монет! 💰 Теперь у вас: {new_balance} монет")

# ========== СЛОТЫ ==========

async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 50
    
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet:
        await update.message.reply_text("❌ Недостаточно монет! Минимальная ставка: 50")
        return
    
    symbols = ['🍒', '🍋', '🍉', '🍀', '💎', '7️⃣']
    reels = [random.choice(symbols) for _ in range(3)]
    
    if reels[0] == reels[1] == reels[2]:
        if reels[0] == '💎': win_multiplier = 10
        elif reels[0] == '7️⃣': win_multiplier = 5
        else: win_multiplier = 3
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win_multiplier = 2
    else:
        win_multiplier = 0
    
    win_amount = bet * win_multiplier
    new_balance = result[0] - bet + win_amount
    
    cursor.execute(
        'UPDATE users SET balance = ? WHERE user_id = ?',
        (new_balance, user_id)
    )
    db.commit()
    
    slots_display = f"🎰 | {reels[0]} | {reels[1]} | {reels[2]} |"
    if win_multiplier == 0:
        result_text = f"❌ Проигрыш! -{bet} монет"
    else:
        result_text = f"🎉 Выигрыш! +{win_amount} монет (x{win_multiplier})"
    
    await update.message.reply_text(
        f"{slots_display}\n{result_text}\n💰 Баланс: {new_balance} монет"
    )

# ========== БЛЭКДЖЕК ==========

def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♥', '♦', '♣', '♠']
    deck = [f'{rank}{suit}' for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def hand_value(hand):
    value = 0
    aces = 0
    
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(rank)
    
    while value > 21 and aces:
        value -= 10
        aces -= 1
    
    return value

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 100
    
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet:
        await update.message.reply_text("❌ Недостаточно монет! Минимальная ставка: 100")
        return
    
    deck = create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    
    cursor.execute(
        'INSERT OR REPLACE INTO blackjack_games (user_id, deck, player_hand, dealer_hand, bet) VALUES (?, ?, ?, ?, ?)',
        (user_id, ','.join(deck), ','.join(player_hand), ','.join(dealer_hand), bet)
    )
    db.commit()
    
    player_value = hand_value(player_hand)
    
    await update.message.reply_text(
        f"🎮 Блэкджек! Ставка: {bet} монет\n\n"
        f"💳 Ваши карты: {', '.join(player_hand)} (очки: {player_value})\n"
        f"🎭 Карта дилера: {dealer_hand[0]} ?\n\n"
        f"Используйте команды:\n"
        f"/hit - Взять карту\n"
        f"/stand - Остановиться"
    )

async def hit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    
    cursor.execute('SELECT deck, player_hand, dealer_hand, bet FROM blackjack_games WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Нет активной игры. Начните с /blackjack")
        return
    
    deck = result[0].split(',')
    player_hand = result[1].split(',')
    dealer_hand = result[2].split(',')
    bet = result[3]
    
    # Игрок берет карту
    player_hand.append(deck.pop())
    player_value = hand_value(player_hand)
    
    if player_value > 21:
        # Игрок проиграл
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bet, user_id))
        cursor.execute('DELETE FROM blackjack_games WHERE user_id = ?', (user_id,))
        db.commit()
        
        await update.message.reply_text(
            f"💥 Перебор! Ваши карты: {', '.join(player_hand)} (очки: {player_value})\n"
            f"❌ Вы проиграли {bet} монет\n"
            f"Карты дилера: {', '.join(dealer_hand)}"
        )
        return
    
    # Обновляем игру
    cursor.execute(
        'UPDATE blackjack_games SET deck = ?, player_hand = ? WHERE user_id = ?',
        (','.join(deck), ','.join(player_hand), user_id)
    )
    db.commit()
    
    await update.message.reply_text(
        f"🎴 Вы взяли карту: {player_hand[-1]}\n"
        f"💳 Ваши карты: {', '.join(player_hand)} (очки: {player_value})\n\n"
        f"Используйте:\n/hit - Взять карту\n/stand - Остановиться"
    )

async def stand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    
    cursor.execute('SELECT deck, player_hand, dealer_hand, bet FROM blackjack_games WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Нет активной игры. Начните с /blackjack")
        return
    
    deck = result[0].split(',')
    player_hand = result[1].split(',')
    dealer_hand = result[2].split(',')
    bet = result[3]
    
    # Дилер берет карты
    dealer_value = hand_value(dealer_hand)
    while dealer_value < 17:
        dealer_hand.append(deck.pop())
        dealer_value = hand_value(dealer_hand)
    
    player_value = hand_value(player_hand)
    
    # Определяем победителя
    if dealer_value > 21:
        result_text = f"🎉 Дилер перебрал! Вы выиграли {bet * 2} монет"
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bet, user_id))
    elif player_value > dealer_value:
        result_text = f"🎉 Вы выиграли! +{bet * 2} монет"
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bet, user_id))
    elif player_value == dealer_value:
        result_text = "🤝 Ничья! Ставка возвращена"
    else:
        result_text = f"❌ Вы проиграли {bet} монет"
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bet, user_id))
    
    cursor.execute('DELETE FROM blackjack_games WHERE user_id = ?', (user_id,))
    db.commit()
    
    await update.message.reply_text(
        f"🎮 Игра завершена!\n"
        f"💳 Ваши карты: {', '.join(player_hand)} (очки: {player_value})\n"
        f"🎭 Карты дилера: {', '.join(dealer_hand)} (очки: {dealer_value})\n\n"
        f"{result_text}"
    )

# ========== КОЛЕСО ФОРТУНЫ ==========

async def wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE message_count > 0')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ В чате пока нет активных участников")
        return
    
    winner_id, winner_username = random.choice(users)
    
    message = await update.message.reply_text("🎡 Колесо фортуны вращается...")
    await asyncio.sleep(2)
    
    await message.edit_text(f"🎉 Колесо фортуны выбирает... @{winner_username}!\nПоздравляем победителя! 🎊")

# ========== ТЕГ ВСЕХ ==========

async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT username FROM users WHERE message_count > 0')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ В чате пока нет активных участников")
        return
    
    mentions = " ".join([f"@{user[0]}" for user in users if user[0]])
    await update.message.reply_text(f"📢 Внимание всем! {mentions}")

# ========== СТАТИСТИКА ==========

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*), SUM(message_count) FROM users')
    total_users, total_messages = cursor.fetchone()
    
    cursor.execute('SELECT username, message_count FROM users WHERE message_count > 0 ORDER BY message_count DESC LIMIT 5')
    top_users = cursor.fetchall()
    
    stats_text = f"📊 Статистика чата:\n👥 Участников: {total_users or 0}\n💬 Сообщений: {total_messages or 0}\n\n🏆 Топ активных:\n"
    for i, (username, count) in enumerate(top_users, 1):
        stats_text += f"{i}. {username}: {count} сообщ.\n"
    
    await update.message.reply_text(stats_text)

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.lower()
    
    cursor = db.cursor()
    
    # Обновляем счетчик сообщений
    cursor.execute(
        'INSERT INTO users (user_id, username, message_count) VALUES (?, ?, 1) '
        'ON CONFLICT(user_id) DO UPDATE SET message_count = message_count + 1',
        (user_id, username)
    )
    
    # Проверка на запрещенные слова
    for word in text.split():
        if word in BAD_WORDS:
            responses = [
                f"🚫 @{username}, у нас тут культурное заведение!",
                f"@{username}, ай-яй-яй! Такой язык не используем!",
                f"Эй, @{username}! Помни о правилах чата!",
            ]
            await update.message.reply_text(random.choice(responses))
            break
    
    # Проверка на специальные реакции
    for trigger, responses in SPECIAL_REACTIONS.items():
        if trigger in text:
            await update.message.reply_text(random.choice(responses))
            break
    
    db.commit()

# ========== ЗАПУСК БОТА ==========

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("bonus", bonus))
    application.add_handler(CommandHandler("slots", slots))
    application.add_handler(CommandHandler("blackjack", blackjack))
    application.add_handler(CommandHandler("hit", hit))
    application.add_handler(CommandHandler("stand", stand))
    application.add_handler(CommandHandler("wheel", wheel))
    application.add_handler(CommandHandler("all", tag_all))
    application.add_handler(CommandHandler("stats", stats))
    
    # Обработчик всех сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🎰 Казино-бот запущен и работает!")
    application.run_polling()

if __name__ == '__main__':
    main()        CREATE TABLE IF NOT EXISTS blackjack_games (
            user_id INTEGER PRIMARY KEY,
            deck TEXT,
            player_hand TEXT,
            dealer_hand TEXT,
            bet INTEGER
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# Списки слов и реакций
BAD_WORDS = ['мат1', 'мат2', 'плохое_слово']  # Замените на свои

SPECIAL_REACTIONS = {
    'шут': ['Парашют!', 'Глеб!', 'Самолет!'],
    '4:20': ['Курить!', 'Взрывай!', 'Взрывай чувак!'],
    'иван': ['Быстров!', 'Иваныч!', 'Ваня!'],
    'привет': ['И тебе привет!', 'Здарова!', 'Приветствую!'],
    'бот': ['Я здесь!', 'На связи!', 'Чем могу помочь?']
}

TIME_MESSAGES = [
    "Время взрывать!",
    "Пора взрывать!", 
    "Time for smoking!",
    "4:20!",
    "Взрывай!!!",
    "Курим чуваки!",
    "Поджигаем косого!"
]

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 1000)',
        (user_id, username)
    )
    db.commit()
    
    await update.message.reply_text(
        f"🎰 Привет {username}! Добро пожаловать в казино-бот!\n\n"
        f"💰 Начальный баланс: 1000 монет\n\n"
        f"🎮 Команды:\n"
        f"/slots - Игра в слоты (ставка 50)\n"
        f"/blackjack - Начать игру в блэкджек\n"
        f"/bonus - Получить бонус 500 монет (раз в час)\n"
        f"/balance - Мой баланс\n"
        f"/wheel - Колесо фортуны\n"
        f"/stats - Статистика чата\n"
        f"/all - Тегнуть всех участников"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        await update.message.reply_text(f"💰 Ваш баланс: {result[0]} монет")
    else:
        await update.message.reply_text("❌ Напишите /start")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    
    cursor.execute('SELECT last_bonus, balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Напишите /start")
        return
    
    last_bonus, balance = result
    now = datetime.now()
    
    if last_bonus:
        last_bonus = datetime.strptime(last_bonus, '%Y-%m-%d %H:%M:%S.%f')
        if now - last_bonus < timedelta(hours=1):
            time_left = timedelta(hours=1) - (now - last_bonus)
            minutes = time_left.seconds // 60
            await update.message.reply_text(f"⏳ Бонус будет доступен через {minutes} минут")
            return
    
    new_balance = balance + 500
    cursor.execute(
        'UPDATE users SET balance = ?, last_bonus = ? WHERE user_id = ?',
        (new_balance, now, user_id)
    )
    db.commit()
    
    await update.message.reply_text(f"🎁 +500 монет! 💰 Теперь у вас: {new_balance} монет")

# ========== СЛОТЫ ==========

async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 50
    
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet:
        await update.message.reply_text("❌ Недостаточно монет! Минимальная ставка: 50")
        return
    
    symbols = ['🍒', '🍋', '🍉', '🍀', '💎', '7️⃣']
    reels = [random.choice(symbols) for _ in range(3)]
    
    if reels[0] == reels[1] == reels[2]:
        if reels[0] == '💎': win_multiplier = 10
        elif reels[0] == '7️⃣': win_multiplier = 5
        else: win_multiplier = 3
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win_multiplier = 2
    else:
        win_multiplier = 0
    
    win_amount = bet * win_multiplier
    new_balance = result[0] - bet + win_amount
    
    cursor.execute(
        'UPDATE users SET balance = ? WHERE user_id = ?',
        (new_balance, user_id)
    )
    db.commit()
    
    slots_display = f"🎰 | {reels[0]} | {reels[1]} | {reels[2]} |"
    if win_multiplier == 0:
        result_text = f"❌ Проигрыш! -{bet} монет"
    else:
        result_text = f"🎉 Выигрыш! +{win_amount} монет (x{win_multiplier})"
    
    await update.message.reply_text(
        f"{slots_display}\n{result_text}\n💰 Баланс: {new_balance} монет"
    )

# ========== БЛЭКДЖЕК ==========

def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♥', '♦', '♣', '♠']
    deck = [f'{rank}{suit}' for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def hand_value(hand):
    value = 0
    aces = 0
    
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(rank)
    
    while value > 21 and aces:
        value -= 10
        aces -= 1
    
    return value

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 100
    
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet:
        await update.message.reply_text("❌ Недостаточно монет! Минимальная ставка: 100")
        return
    
    deck = create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    
    cursor.execute(
        'INSERT OR REPLACE INTO blackjack_games (user_id, deck, player_hand, dealer_hand, bet) VALUES (?, ?, ?, ?, ?)',
        (user_id, ','.join(deck), ','.join(player_hand), ','.join(dealer_hand), bet)
    )
    db.commit()
    
    player_value = hand_value(player_hand)
    dealer_card = dealer_hand[0]
    
    keyboard = [
        ['🎯 Взять', '✋ Стоять'],
        ['❌ Отмена']
    ]
    
    await update.message.reply_text(
        f"🎮 Блэкджек! Ставка: {bet} монет\n\n"
        f"💳 Ваши карты: {', '.join(player_hand)} (очки: {player_value})\n"
        f"🎭 Карта дилера: {dealer_card} ?\n\n"
        f"Выберите действие:",
        reply_markup={
            'keyboard': keyboard,
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
    )

# ========== КОЛЕСО ФОРТУНЫ ==========

async def wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE message_count > 0')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ В чате пока нет активных участников")
        return
    
    winner_id, winner_username = random.choice(users)
    
    message = await update.message.reply_text("🎡 Колесо фортуны вращается...")
    await asyncio.sleep(2)
    
    await message.edit_text(f"🎉 Колесо фортуны выбирает... @{winner_username}!\nПоздравляем победителя! 🎊")

# ========== ТЕГ ВСЕХ ==========

async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT username FROM users WHERE message_count > 0')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ В чате пока нет активных участников")
        return
    
    mentions = " ".join([f"@{user[0]}" for user in users if user[0]])
    await update.message.reply_text(f"📢 Внимание всем! {mentions}")

# ========== СТАТИСТИКА ==========

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*), SUM(message_count) FROM users')
    total_users, total_messages = cursor.fetchone()
    
    cursor.execute('SELECT username, message_count FROM users WHERE message_count > 0 ORDER BY message_count DESC LIMIT 5')
    top_users = cursor.fetchall()
    
    stats_text = f"📊 Статистика чата:\n👥 Участников: {total_users or 0}\n💬 Сообщений: {total_messages or 0}\n\n🏆 Топ активных:\n"
    for i, (username, count) in enumerate(top_users, 1):
        stats_text += f"{i}. {username}: {count} сообщ.\n"
    
    await update.message.reply_text(stats_text)

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.lower()
    
    cursor = db.cursor()
    
    # Обновляем счетчик сообщений
    cursor.execute(
        'INSERT INTO users (user_id, username, message_count) VALUES (?, ?, 1) '
        'ON CONFLICT(user_id) DO UPDATE SET message_count = message_count + 1',
        (user_id, username)
    )
    
    # Проверка на запрещенные слова
    for word in text.split():
        if word in BAD_WORDS:
            responses = [
                f"🚫 @{username}, у нас тут культурное заведение!",
                f"@{username}, ай-яй-яй! Такой язык не используем!",
                f"Эй, @{username}! Помни о правилах чата!",
            ]
            await update.message.reply_text(random.choice(responses))
            break
    
    # Проверка на специальные реакции
    for trigger, responses in SPECIAL_REACTIONS.items():
        if trigger in text:
            await update.message.reply_text(random.choice(responses))
            break
    
    db.commit()

# ========== ЕЖЕДНЕВНОЕ СООБЩЕНИЕ ==========

async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    message = random.choice(TIME_MESSAGES)
    print(f"Время отправить сообщение: {message}")

# ========== ЗАПУСК БОТА ==========

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("bonus", bonus))
    application.add_handler(CommandHandler("slots", slots))
    application.add_handler(CommandHandler("blackjack", blackjack))
    application.add_handler(CommandHandler("wheel", wheel))
    application.add_handler(CommandHandler("all", tag_all))
    application.add_handler(CommandHandler("stats", stats))
    
    # Обработчик всех сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🎰 Казино-бот запущен и работает!")
    application.run_polling()

if __name__ == '__main__':
    main()            user_id INTEGER,
            word TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_stats (
            word TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# Списки слов
BAD_WORDS = ['мат1', 'мат2', 'плохое_слово']  # Замените на свои
SPECIAL_WORDS = {
    'шут': 'шут-парашют!',
    'привет': 'И тебе привет, дружище!',
    'код': 'Код — это поэзия, понятная компьютерам!'
}

TIME_MESSAGES = [
    "Время взрывать!",
    "Пора взрывать!", 
    "Time for smoking!",
    "4:20!",
    "Взрывай!!!",
    "Курим чуваки!",
    "Поджигаем косого!"
]

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 1000)',
        (user_id, username)
    )
    db.commit()
    
    await update.message.reply_text(
        f"Привет {username}! Добро пожаловать в нашего бота!\n"
        f"Команды:\n/slots - Игра в слоты\n/bonus - Бонус (раз в 3 часа)\n/balance - Баланс\n/wheel - Колесо фортуны\n/stats - Статистика чата"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        await update.message.reply_text(f"💰 Баланс: {result[0]} монет")
    else:
        await update.message.reply_text("❌ Напишите /start")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db.cursor()
    
    cursor.execute('SELECT last_bonus, balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Напишите /start")
        return
    
    last_bonus, balance = result
    now = datetime.now()
    
    if last_bonus:
        last_bonus = datetime.strptime(last_bonus, '%Y-%m-%d %H:%M:%S.%f')
        if now - last_bonus < timedelta(hours=3):
            time_left = timedelta(hours=3) - (now - last_bonus)
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            await update.message.reply_text(f"⏳ Бонус через {hours}ч {minutes}м")
            return
    
    new_balance = balance + 500
    cursor.execute(
        'UPDATE users SET balance = ?, last_bonus = ? WHERE user_id = ?',
        (new_balance, now, user_id)
    )
    db.commit()
    
    await update.message.reply_text(f"🎁 +500 монет! Всего: {new_balance}")

async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 50
    
    cursor = db.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet:
        await update.message.reply_text("❌ Недостаточно монет!")
        return
    
    symbols = ['🍒', '🍋', '🍉', '🍀', '💎', '7️⃣']
    reels = [random.choice(symbols) for _ in range(3)]
    
    if reels[0] == reels[1] == reels[2]:
        if reels[0] == '💎': win_multiplier = 10
        elif reels[0] == '7️⃣': win_multiplier = 5
        else: win_multiplier = 3
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win_multiplier = 2
    else:
        win_multiplier = 0
    
    win_amount = bet * win_multiplier
    new_balance = result[0] - bet + win_amount
    
    cursor.execute(
        'UPDATE users SET balance = ? WHERE user_id = ?',
        (new_balance, user_id)
    )
    db.commit()
    
    slots_display = f"🎰 | {reels[0]} | {reels[1]} | {reels[2]} |"
    result_text = f"❌ Проигрыш! -{bet}" if win_multiplier == 0 else f"🎉 Выигрыш! +{win_amount}"
    
    await update.message.reply_text(
        f"{slots_display}\n{result_text}\n💰 Баланс: {new_balance}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.lower()
    words = text.split()
    
    cursor = db.cursor()
    
    cursor.execute(
        'INSERT INTO users (user_id, username, message_count) VALUES (?, ?, 1) '
        'ON CONFLICT(user_id) DO UPDATE SET message_count = message_count + 1',
        (user_id, username)
    )
    
    for word in words:
        if word in BAD_WORDS:
            cursor.execute(
                'INSERT INTO violations (user_id, word) VALUES (?, ?)',
                (user_id, word)
            )
            cursor.execute(
                'INSERT INTO word_stats (word, count) VALUES (?, 1) '
                'ON CONFLICT(word) DO UPDATE SET count = count + 1',
                (word,)
            )
            db.commit()
            
            responses = [
                f"🚫 @{username}, у нас тут культурное заведение!",
                f"@{username}, ай-яй-яй! Такой язык не используем!",
            ]
            await update.message.reply_text(random.choice(responses))
            break
        
        if word in SPECIAL_WORDS:
            await update.message.reply_text(SPECIAL_WORDS[word])
            break

async def wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE message_count > 0')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ Нет активных участников")
        return
    
    winner_id, winner_username = random.choice(users)
    message = await update.message.reply_text("🎡 Колесо фортуны вращается...")
    await asyncio.sleep(2)
    await message.edit_text(f"🎉 Победитель: @{winner_username}!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*), SUM(message_count) FROM users')
    total_users, total_messages = cursor.fetchone()
    
    cursor.execute('SELECT username, message_count FROM users WHERE message_count > 0 ORDER BY message_count DESC LIMIT 5')
    top_users = cursor.fetchall()
    
    cursor.execute('SELECT word, count FROM word_stats ORDER BY count DESC LIMIT 5')
    top_bad_words = cursor.fetchall()
    
    stats_text = f"📊 Статистика чата:\n👥 Участников: {total_users or 0}\n💬 Сообщений: {total_messages or 0}\n\n🏆 Топ активных:\n"
    for i, (username, count) in enumerate(top_users, 1):
        stats_text += f"{i}. {username}: {count} сообщ.\n"
    
    if top_bad_words:
        stats_text += "\n🚫 Популярные запрещенные слова:\n"
        for word, count in top_bad_words:
            stats_text += f"• {word}: {count} раз\n"
    
    await update.message.reply_text(stats_text)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("bonus", bonus))
    application.add_handler(CommandHandler("slots", slots))
    application.add_handler(CommandHandler("wheel", wheel))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен и работает!")
    application.run_polling()

if __name__ == '__main__':
    main()
