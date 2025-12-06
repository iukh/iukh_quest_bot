import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import json
import os
from datetime import datetime
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Структура вопроса
@dataclass
class Question:
    id: int
    text: str
    answer: str
    hint1: str
    hint2: str
    description: str
    image_url: Optional[str] = None

class UserDebt:
    """Класс для хранения долгов за подсказки"""
    def __init__(self):
        self.hugs = 0  # минуты обнимашек
        self.kisses = 0  # количество поцелуев
        self.wishes = 0  # количество желаний автора
        
    def add_hugs(self, minutes: int = 5):
        """Добавить обнимашки"""
        self.hugs += minutes
        
    def add_kisses(self, count: int = 10):
        """Добавить поцелуи"""
        self.kisses += count
        
    def add_wish(self, count: int = 1):
        """Добавить желание автора"""
        self.wishes += count
        
    def to_dict(self):
        return {
            'hugs': self.hugs,
            'kisses': self.kisses,
            'wishes': self.wishes
        }
    
    @classmethod
    def from_dict(cls, data):
        debt = cls()
        debt.hugs = data.get('hugs', 0)
        debt.kisses = data.get('kisses', 0)
        debt.wishes = data.get('wishes', 0)
        return debt
    
    def __str__(self):
        result = []
        if self.hugs > 0:
            result.append(f"💖 Обнимашки: {self.hugs} минут")
        if self.kisses > 0:
            result.append(f"💋 Поцелуи: {self.kisses} штук")
        if self.wishes > 0:
            result.append(f"🎁 Желания: {self.wishes} шт")
        return "\n".join(result) if result else "🎉 Долгов нет!"

class UserProgress:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_question = 1
        self.used_hints: Dict[int, list] = {}  # какие подсказки использованы
        self.showed_solutions: list = []  # номера вопросов, где показано решение
        self.questions_without_hints = []  # номера вопросов, пройденных без подсказок
        self.debt = UserDebt()  # Изначально долг равен 0
        self.start_time = datetime.now().isoformat()
        
    def add_hint_used(self, question_id: int, hint_num: int):
        """Добавить использованную подсказку"""
        # Инициализируем список для вопроса, если его нет
        if question_id not in self.used_hints:
            self.used_hints[question_id] = []
            
        if hint_num not in self.used_hints[question_id]:
            self.used_hints[question_id].append(hint_num)
            
            # Добавляем "долг" за подсказку
            if hint_num == 1:
                self.debt.add_hugs(5)
            elif hint_num == 2:
                self.debt.add_kisses(10)
    
    def add_solution_shown(self, question_id: int):
        """Добавить просмотр решения"""
        if question_id not in self.showed_solutions:
            self.showed_solutions.append(question_id)
            # Добавляем долг за просмотр решения
            self.debt.add_wish(1)
    
    def mark_question_completed(self, question_id: int):
        """Отметить вопрос как завершенный и проверить, были ли подсказки"""
        used = self.used_hints.get(question_id, [])
        if not used:
            self.questions_without_hints.append(question_id)
    
    def get_stats(self) -> Tuple[int, int]:
        """Возвращает статистику: (всего пройдено, без подсказок)"""
        total_completed = self.current_question - 1
        without_hints = len(self.questions_without_hints)
        return total_completed, without_hints
        
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'current_question': self.current_question,
            'used_hints': self.used_hints,
            'showed_solutions': self.showed_solutions,
            'questions_without_hints': self.questions_without_hints,
            'debt': self.debt.to_dict(),
            'start_time': self.start_time
        }
    
    @classmethod
    def from_dict(cls, data):
        progress = cls(data['user_id'])
        progress.current_question = data['current_question']
        progress.used_hints = data.get('used_hints', {})
        progress.showed_solutions = data.get('showed_solutions', [])
        progress.questions_without_hints = data.get('questions_without_hints', [])
        progress.debt = UserDebt.from_dict(data.get('debt', {}))
        progress.start_time = data.get('start_time', datetime.now().isoformat())
        return progress

# Вопросы для квеста
QUESTIONS = [
    Question(
        id=1,
        description="Первая загадка",
        text="Что падает с неба зимой, но не является снегом, если это светит?",
        answer="снежинка",
        hint1="Это бывает разной формы",
        hint2="У каждой из них уникальный узор",
        image_url="https://images.unsplash.com/photo-1544717305-2782549b5136?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=2,
        description="Вторая загадка",
        text="Расшифруй ответ: \n eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InF1ZXN0X3VzZXJfMTIzNCIsImVtYWlsIjoicXVlc3QuZW1haWxAZXhhbXBsZS5jb20iLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTIzNDU2NzgsImlhdCI6MTcxMjM0MjA3OCwiYW5zd2VyIjoiY29uZ3JhdHVsYXRpb25zIiwicmFuZG9tX251bWJlciI6ODQ3Miwic2Vzc2lvbl9pZCI6InNlc3NfYWJjZDM0NWVmMTIzIn0.6jSy1IJ0q2n4GDwV2DgvQaJXkL3O9bHpQwM8zKtN7YxE",
        answer="congratulations",
        hint1="Ты ж программист =)",
        hint2="Кажется это какой-то токен",
        image_url="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=3,
        description="Третья загадка",
        text="А что спряталось тут? НГИОСЕКВ",
        answer="снеговик",
        hint1="Наше 'любимое' задание)",
        hint2="Это анаграмма, ответ связан с зимой и снегом. Видели это на пути в кондитерскую)",
        image_url="https://images.unsplash.com/photo-1533134486753-c833f0ed4866?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=4,
        description="Четвертая загадка",
        text="Я нечетное число, убери одну букву и я стану четным",
        answer="seven",
        hint1="Ответ на английском",
        hint2="Число от 0 до 10",
        image_url="https://images.unsplash.com/photo-1500382017468-9049fed747ef?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=5,
        description="Пятая загадка",
        text="Что имеет ключ, но не может открыть замок?",
        answer="пианино",
        hint1="Музыкальный инструмент",
        hint2="На нем играют, нажимая клавиши",
        image_url="https://images.unsplash.com/photo-1549399542-7e3f8b79c341?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=6,
        description="Шестая загадка",
        text="Что летает без крыльев и плачет без глаз?",
        answer="облако",
        hint1="Белое и пушистое на небе",
        hint2="Из него идет дождь",
        image_url="https://images.unsplash.com/photo-1584820927498-cfe5211fd8bf?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=7,
        description="Седьмая загадка",
        text="Что можно разбить, даже не прикасаясь к нему?",
        answer="сердце",
        hint1="Связано с чувствами",
        hint2="Символ любви",
        image_url="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=8,
        description="Восьмая загадка",
        text="Что становится больше, если его перевернуть?",
        answer="шесть",
        hint1="Это цифра",
        hint2="Превращается в другую цифру",
        image_url="https://images.unsplash.com/photo-1505142468610-359e7d316be0?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=9,
        description="Девятая загадка",
        text="Что можно держать в правой руке, но никогда в левой?",
        answer="левый локоть",
        hint1="Часть тела",
        hint2="Связано с локтями",
        image_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    ),
    Question(
        id=10,
        description="Десятая загадка",
        text="Что принадлежит тебе, но другие используют его чаще, чем ты?",
        answer="имя",
        hint1="Тебе дали его при рождении",
        hint2="К тебе обращаются с помощью этого",
        image_url="https://images.unsplash.com/photo-1451187580459-43490279c0fa?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
    )
]

class QuestBot:
    def __init__(self):
        self.user_progress: Dict[int, UserProgress] = {}
        self.load_progress()
        
    def save_progress(self):
        """Сохраняет прогресс всех пользователей в файл"""
        data = {user_id: progress.to_dict() 
                for user_id, progress in self.user_progress.items()}
        with open('progress.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_progress(self):
        """Загружает прогресс из файла"""
        if os.path.exists('progress.json'):
            try:
                with open('progress.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_data in data.values():
                        progress = UserProgress.from_dict(user_data)
                        self.user_progress[progress.user_id] = progress
                logger.info("Прогресс загружен из файла")
            except Exception as e:
                logger.error(f"Ошибка загрузки прогресса: {e}")
    
    def get_user_progress(self, user_id: int) -> UserProgress:
        """Получает или создает прогресс пользователя"""
        if user_id not in self.user_progress:
            self.user_progress[user_id] = UserProgress(user_id)
        return self.user_progress[user_id]
    
    def get_current_question(self, user_id: int) -> Optional[Question]:
        """Получает текущий вопрос для пользователя"""
        progress = self.get_user_progress(user_id)
        if 1 <= progress.current_question <= len(QUESTIONS):
            return QUESTIONS[progress.current_question - 1]
        return None
    
    def get_question_keyboard(self, user_id: int, question_id: int):
        """Создает клавиатуру с подсказками и решением для вопроса"""
        progress = self.get_user_progress(user_id)
        used_hints = progress.used_hints.get(question_id, [])
        
        buttons = []
        
        # Кнопки подсказок
        if 1 not in used_hints:
            buttons.append([InlineKeyboardButton("💖 Подсказка 1 (+5 мин обнимашек)", callback_data=f"hint_{question_id}_1")])
        if 2 not in used_hints:
            buttons.append([InlineKeyboardButton("💋 Подсказка 2 (+10 поцелуев)", callback_data=f"hint_{question_id}_2")])
        
        # Кнопка решения (появляется только после обеих подсказок)
        if len(used_hints) >= 2 and question_id not in progress.showed_solutions:
            buttons.append([InlineKeyboardButton("🔴 Решение (+1 желание)", callback_data=f"solution_{question_id}")])
            
        return InlineKeyboardMarkup(buttons) if buttons else None
    
    def get_question_text(self, user_id: int, question: Question) -> str:
        """Формирует текст вопроса со статистикой и использованными подсказками"""
        progress = self.get_user_progress(user_id)
        total_completed, without_hints = progress.get_stats()
        used_hints = progress.used_hints.get(question.id, [])
        
        text = (
            f"❓{question.description}❓\n\n"
            f"{question.text}\n\n"
        )
        
        # Показываем использованные подсказки
        if 1 in used_hints:
            text += f"💡 *Подсказка 1:* {question.hint1}\n"
        if 2 in used_hints:
            text += f"💡 *Подсказка 2:* {question.hint2}\n"
        
        if used_hints:
            text += "\n"
        
        text += (
            f"📊 Прогресс: {total_completed}/{len(QUESTIONS)}\n"
            f"✅ Без подсказок: {without_hints} вопросов\n"
        )
        
        debt_str = str(progress.debt)
        if debt_str != "🎉 Долгов нет!":
            text += f"\n💝 Текущий долг:\n{debt_str}\n"
        
        return text

async def send_message(update: Update, text: str, parse_mode: str = 'Markdown', reply_markup = None):
    """Универсальная функция для отправки сообщений"""
    if update.message:
        return await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.callback_query:
        return await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.effective_message:
        return await update.effective_message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    progress = bot.get_user_progress(user.id)
    
    welcome_text = (
        f"🎄 Привет, {user.first_name}!\n\n"
        f"✨ Добро пожаловать в зимний квест:\n"
        f"🩵 *В ожидании встречи* 🩵\n\n"
        f"Тебя ждут {len(QUESTIONS)} загадок!\n\n"
        f"💖 *Особые правила:*\n"
        f"• За первую подсказку: +5 минут обнимашек ёжика 🤗\n"
        f"• За вторую подсказку: +10 поцелуев ёжика 🤗\n"
        f"• За решение (после обеих подсказок): +1 исполнение желания ёжика 🤗\n\n"
        f"🎅🏻 *Как играть:*\n"
        f"1. Отвечай на загадки, отправляя ответ в чат\n"
        f"2. Если сложно - используй подсказки (кнопки ниже)\n"
        f"3. После обеих подсказок появится кнопка 'Решение'\n"
        f"4. Все ответы вводятся маленькими буквами\n\n"
    )
    
    # Всегда показываем welcome_text
    await send_message(update, welcome_text, parse_mode='Markdown')
    
    # Если квест уже завершен
    if progress.current_question > len(QUESTIONS):
        await send_message(update, "🎉 Ты уже завершил квест! Нажми /restart чтобы начать заново.")
        return
    
    # Показываем текущий вопрос
    question = bot.get_current_question(user.id)
    
    if question:
        text = bot.get_question_text(user.id, question)
        keyboard = bot.get_question_keyboard(user.id, question.id)
        await send_message(update, text, reply_markup=keyboard, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (ответов на вопросы)"""
    user = update.effective_user
    message_text = update.message.text.strip().lower()
    bot: QuestBot = context.bot_data['quest_bot']
    
    progress = bot.get_user_progress(user.id)
    question = bot.get_current_question(user.id)
    
    if not question:
        await update.message.reply_text("🎉 Квест завершен! Нажми /restart чтобы начать заново.")
        return
    
    # Проверка ответа
    if message_text == question.answer.lower():
        # Отмечаем вопрос как пройденный и проверяем подсказки
        progress.mark_question_completed(question.id)
        progress.current_question += 1
        
        # Проверяем, есть ли еще вопросы
        if progress.current_question <= len(QUESTIONS):
            await show_next_question(update, context, user.id)
        else:
            # Квест завершен
            await show_final_results(update, progress)
        
        bot.save_progress()
    else:
        await update.message.reply_text("❌ Неправильно. Попробуй еще раз! \n\n Или может стоит воспользоваться подсказкой? 😉 ")

async def show_next_question(update, context, user_id):
    """Показать следующий вопрос"""
    bot: QuestBot = context.bot_data['quest_bot']
    
    next_question = bot.get_current_question(user_id)
    text = bot.get_question_text(user_id, next_question)
    keyboard = bot.get_question_keyboard(user_id, next_question.id)
    
    await send_message(update, text, reply_markup=keyboard, parse_mode='Markdown')

async def show_final_results(update, progress):
    """Показать финальные результаты"""
    total_completed, without_hints = progress.get_stats()
    
    response = (
        f"🎄🎅🎉 *ПОЗДРАВЛЯЮ С ЗАВЕРШЕНИЕМ КВЕСТА!* 🎉🎅🎄\n\n"
        f"Ты успешно прошел все {len(QUESTIONS)} новогодних загадок!\n\n"
        f"📊 *Итоговая статистика:*\n"
        f"• 🎯 Пройдено вопросов: {total_completed}\n"
        f"• ✅ Без подсказок: {without_hints}\n"
        f"• 💡 С подсказками: {total_completed - without_hints}\n\n"
        f"💝 *Твой новогодний долг:*\n{progress.debt}\n\n"
    )
    
    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        response += (
            f"❄️ *Новогодний бонус:*\n"
            f"Все обещания нужно выполнить до боя курантов!\n"
            f"Это сделает вашу встречу Нового года волшебной! 🎇\n\n"
        )
    else:
        response += (
            f"🏆 *ВАУ! Идеальный результат!*\n"
            f"Ты прошел весь квест без единой подсказки!\n"
            f"Ты заслужил особый новогодний сюрприз! 🎁\n\n"
        )
    
    response += (
        f"✨ *С наступающим Новым Годом!*\n"
        f"Пусть он будет полон любви и тепла! ❤️\n\n"
        f"Нажми /restart чтобы пройти квест еще раз!"
    )
    
    await send_message(update, response, parse_mode='Markdown')

async def handle_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на подсказки"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    # Извлекаем данные из callback_data
    try:
        _, question_id_str, hint_num_str = query.data.split('_')
        question_id = int(question_id_str)
        hint_num = int(hint_num_str)
    except ValueError:
        logger.error(f"Неверный формат callback_data: {query.data}")
        return
    
    progress = bot.get_user_progress(user.id)
    question = QUESTIONS[question_id - 1]
    
    # Проверяем, что пользователь на текущем вопросе
    if progress.current_question != question_id:
        await query.edit_message_text(
            text="Этот вопрос уже пройден. Продолжай текущий вопрос!",
            reply_markup=None
        )
        return
    
    # Добавляем подсказку в использованные
    progress.add_hint_used(question_id, hint_num)
    
    # Формируем новый текст сообщения
    text = bot.get_question_text(user.id, question)
    
    # Обновляем клавиатуру
    keyboard = bot.get_question_keyboard(user.id, question_id)
    
    # ОБНОВЛЯЕМ СООБЩЕНИЕ
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении сообщения: {e}")
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    bot.save_progress()

async def handle_solution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопку 'Решение'"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    # Извлекаем данные из callback_data
    try:
        _, question_id_str = query.data.split('_')
        question_id = int(question_id_str)
    except ValueError:
        logger.error(f"Неверный формат callback_data: {query.data}")
        return
    
    progress = bot.get_user_progress(user.id)
    question = QUESTIONS[question_id - 1]
    
    # Проверяем, что пользователь на текущем вопросе
    if progress.current_question != question_id:
        await query.edit_message_text(
            text="Этот вопрос уже пройден. Продолжай текущий вопрос!",
            reply_markup=None
        )
        return
    
    # Проверяем, что обе подсказки использованы
    used_hints = progress.used_hints.get(question_id, [])
    if len(used_hints) < 2:
        await query.answer("Сначала используй обе подсказки!", show_alert=True)
        return
    
    # Добавляем просмотр решения
    progress.add_solution_shown(question_id)
    
    # Отмечаем вопрос как пройденный (так как показано решение)
    progress.mark_question_completed(question_id)
    progress.current_question += 1
    
    # Формируем сообщение с решением
    text = bot.get_question_text(user.id, question)
    text += f"\n🔴 *Решение:* {question.answer}"
    
    # Создаем сообщение о наказании
    penalty_text = (
        "🎁 *Ты проиграл одно желание!*\n\n"
        "💌 *Что это значит:*\n"
        "Ёжик может загадать одно желание,\n"
        "которое тебе нужно будет выполнить! ❤"
    )
    
    # Обновляем сообщение с вопросом и решением
    await query.edit_message_text(
        text=text,
        reply_markup=None,
        parse_mode='Markdown'
    )
    
    # Отправляем сообщение о наказании
    await query.message.reply_text(penalty_text, parse_mode='Markdown')
    
    # Проверяем, есть ли еще вопросы
    if progress.current_question <= len(QUESTIONS):
        # Пауза перед показом следующего вопроса
        await asyncio.sleep(2)
        
        # Показываем следующий вопрос
        next_question = bot.get_current_question(user.id)
        if next_question:
            next_text = bot.get_question_text(user.id, next_question)
            next_keyboard = bot.get_question_keyboard(user.id, next_question.id)
            await query.message.reply_text(next_text, reply_markup=next_keyboard, parse_mode='Markdown')
    else:
        # Квест завершен
        await show_final_results_from_query(query, progress)
    
    bot.save_progress()

async def show_final_results_from_query(query, progress):
    """Показать финальные результаты из callback query"""
    total_completed, without_hints = progress.get_stats()
    
    response = (
        f"🎄🎅🎉 *ПОЗДРАВЛЯЮ С ЗАВЕРШЕНИЕМ КВЕСТА!* 🎉🎅🎄\n\n"
        f"Ты успешно прошел все {len(QUESTIONS)} новогодних загадок!\n\n"
        f"📊 *Итоговая статистика:*\n"
        f"• 🎯 Пройдено вопросов: {total_completed}\n"
        f"• ✅ Без подсказок: {without_hints}\n"
        f"• 💡 С подсказками: {total_completed - without_hints}\n\n"
        f"💝 *Твой новогодний долг:*\n{progress.debt}\n\n"
    )
    
    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        response += (
            f"❄️ *Новогодний бонус:*\n"
            f"Все обещания нужно выполнить до боя курантов!\n"
            f"Это сделает вашу встречу Нового года волшебной! 🎇\n\n"
        )
    else:
        response += (
            f"🏆 *ВАУ! Идеальный результат!*\n"
            f"Ты прошел весь квест без единой подсказки!\n"
            f"Ты заслужил особый новогодний сюрприз! 🎁\n\n"
        )
    
    response += (
        f"✨ *С наступающим Новым Годом!*\n"
        f"Пусть он будет полон любви и тепла! ❤️\n\n"
        f"Нажми /restart чтобы пройти квест еще раз!"
    )
    
    await query.message.reply_text(response, parse_mode='Markdown')

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс прогресса и начало заново"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    # Сбрасываем прогресс
    bot.user_progress[user.id] = UserProgress(user.id)
    bot.save_progress()
    
    response_text = (
        "🔄 Прогресс сброшен! Все новогодние долги обнулены.\n"
        "Нажми /start чтобы начать квест заново! 🎄"
    )
    
    # Используем универсальную функцию отправки
    await send_message(update, response_text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подробную статистику"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    progress = bot.get_user_progress(user.id)
    total_completed, without_hints = progress.get_stats()
    
    if progress.current_question > len(QUESTIONS):
        stats_text = (
            f"🎄 *Квест завершен!*\n\n"
            f"📊 *Итоговая статистика:*\n"
            f"• 🎯 Пройдено вопросов: {total_completed}/{len(QUESTIONS)}\n"
            f"• ✅ Без подсказок: {without_hints}\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"💝 *Новогодний долг:*\n{progress.debt}\n\n"
        )
        
        if progress.debt.hugs == 0 and progress.debt.kisses == 0 and progress.debt.wishes == 0:
            stats_text += "🏆 *Идеальный результат!* Ты прошел квест без долгов!\n\n"
        
        stats_text += "Нажми /restart чтобы начать заново."
    else:
        question = bot.get_current_question(user.id)
        current_hints = len(progress.used_hints.get(progress.current_question, []))
        
        stats_text = (
            f"🎄 *Новогодний квест: В ожидании встречи*\n\n"
            f"📊 *Статистика:*\n"
            f"• 🏁 Прогресс: {total_completed}/{len(QUESTIONS)}\n"
            f"• ✅ Без подсказок: {without_hints} вопросов\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"🎯 *Текущий вопрос:* {progress.current_question}\n"
            f"🔍 Использовано подсказок: {current_hints}/2\n\n"
            f"💝 *Зимний долг:*\n{progress.debt}\n\n"
        )
        
        if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
            stats_text += (
                "❄️ *Напоминание:*\n"
                "Каждая подсказка и решение - это обещание любви!\n"
                "Выполни все до боя курантов! 🎇\n\n"
            )
        
        stats_text += f"❓ *Текущая загадка:* {question.text[:60]}..."
    
    await send_message(update, stats_text, parse_mode='Markdown')

async def debt_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о долгах"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    progress = bot.get_user_progress(user.id)
    total_completed, without_hints = progress.get_stats()
    
    debt_text = (
        f"🎄 *Зимний долг тепла:*\n\n"
        f"{progress.debt}\n\n"
    )
    
    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        debt_text += (
            f"📊 *Контекст:*\n"
            f"• 🎯 Пройдено вопросов: {total_completed}\n"
            f"• ✅ Без подсказок: {without_hints}\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"❄️ *Важно:*\n"
            f"Все обещания нужно выполнить при первой встрече!💕\n"
        )
    else:
        debt_text += (
            f"🎉 *Ура! У тебя нет долгов!*\n"
            f"Ты молодец! Продолжай в том же духе!\n\n"
            f"📊 Статистика: {without_hints}/{total_completed} без подсказок\n\n"
        )
    
    await send_message(update, debt_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь по командам"""
    help_text = (
        "🎄 *Зимний квест: В ожидании встречи*\n\n"
        "📋 *Доступные команды:*\n\n"
        "/start - Начать или продолжить квест\n"
        "/restart - Начать квест заново (обнуляет долги)\n"
        "/stats - Подробная статистика\n"
        "/debt - Показать текущий долг\n"
        "/help - Показать это сообщение\n\n"
        "💖 *Особые правила квеста:*\n"
        "1. Отвечай на загадки, отправляя ответы текстом\n"
        "2. Если нужна помощь - используй подсказки:\n"
        "   • 💖 Первая подсказка: +5 минут обнимашек твоего ёжика\n"
        "   • 💋 Вторая подсказка: +10 поцелуев для ёжика\n"
        "3. После обеих подсказок появляется кнопка:\n"
        "   • 🔴 Решение: +1 исполнение желания ёжика\n"
        "4. Чем меньше подсказок - тем лучше результат!\n"
        "5. Все долги нужно выполнить при первой встрече! ⏰\n\n"
        "📝 *Важно:*\n"
        "• Ответы вводи строчными буквами\n"
        "• Без лишних символов и пробелов\n"
        "• Прогресс сохраняется автоматически\n\n"
        "🩵 *Скучаю по тебе и жду встречи!* 🩵"
    )
    
    await send_message(update, help_text, parse_mode='Markdown')

async def clear_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отметки выполнения долгов"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']
    
    progress = bot.get_user_progress(user.id)
    old_debt = str(progress.debt)
    
    # Обнуляем долги
    progress.debt = UserDebt()
    bot.save_progress()
    
    response = (
        f"💝 *Долги выполнены!*\n\n"
        f"🎁 *Было:* {old_debt}\n"
        f"✨ *Стало:* {progress.debt}\n\n"
        f"Молодец! Все обещания выполнены! 💕\n"
    )
    
    await send_message(update, response, parse_mode='Markdown')

def main():
    """Запуск бота"""
    # Токен вашего бота
    TOKEN = "8286027833:AAEjA4ajUXyNuOvhiR8Xsbm_9JuNORuuDHk"
    
    # Создаем приложение
    application = Application.builder() \
                    .token(TOKEN) \
                    .build()
    
    # Создаем экземпляр бота и сохраняем в bot_data
    quest_bot = QuestBot()
    application.bot_data['quest_bot'] = quest_bot
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("debt", debt_info))
    application.add_handler(CommandHandler("clear_debt", clear_debt))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик подсказок
    application.add_handler(CallbackQueryHandler(handle_hint, pattern=r"^hint_"))
    
    # Обработчик решений
    application.add_handler(CallbackQueryHandler(handle_solution, pattern=r"^solution_"))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    logger.info("🎄 Зимний квест-бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
