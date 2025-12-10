import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import asyncio

# Настройка основного логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка логирования действий пользователей
user_actions_logger = logging.getLogger('user_actions')
user_actions_logger.setLevel(logging.INFO)

# Создаем обработчик для записи в файл
file_handler = logging.FileHandler('user_actions.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Формат для логов действий пользователей
action_formatter = logging.Formatter('%(asctime)s - USER:%(user_id)d - ACTION:%(action)s - DETAILS:%(details)s')
file_handler.setFormatter(action_formatter)

# Добавляем обработчик к логгеру
user_actions_logger.addHandler(file_handler)
# Отключаем передачу сообщений родительскому логгеру
user_actions_logger.propagate = False


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


# Уникальные поздравления для каждого вопроса
CONGRATULATIONS = {
    1: "🧡 *Отлично!* Ты разгадал первую загадку! 🧡\n\n💛 В этой игре нет приза, но хочется поблагодарить тебя за твое участие небольшими приятностями)\n*Время открыть пакетик с номером 1.* 💕 \nВероятнее всего местоположение пакетиков уже было спалено, но если нет, то изучи шкафы)",
    2: "🧡 *Великолепно!* 🧡️\n\n💛 Время открыть пакетик с номером 2 💕",
    3: "🧡 *Браво!* 🧡\n\n💛 Время открыть пакетик с пакетик 3 💕",
    4: "🧡 *Потрясающе!* 🧡\n\n💛 Время открыть пакетик с номером 4 💕",
    5: "🧡 *Восхитительно!* 🧡\n\n💛 Время открыть пакетик с номером 5 💕",
    6: "🧡 *Замечательно!* 🧡\n\n💛 Время открыть пакетик с номером 6 💕",
    7: "🧡 *Прекрасно!* 🧡\n\n💛 Время открыть пакетик с номером 7 💕",
    8: "🧡 *Гениально!* 🧡\n\n💛 Время открыть пакетик с номером 8 💕",
    9: "🧡 *Умопомрачительно!* 🧡\n\n💛 Время открыть пакетик с номером 9 💕",
    10: "🧡 *Блестяще!* 🧡\n\n💛 Время открыть пакетик с номером 10 💕"
}

# Уникальные ободряющие сообщения после показа решения
ENCOURAGEMENTS = {
    1: "💛 В этой игре нет приза, но хочется поблагодарить тебя за твое участие небольшими приятностями) \n*Время открыть пакетик с номером 1.* 💕",
    2: "💛 *Время открыть пакетик с номером 2* 💕",
    3: "💛 *Время открыть пакетик с номером 3* 💕",
    4: "💛 *Время открыть пакетик с номером 4* 💕",
    5: "💛 *Время открыть пакетик с номером 5* 💕",
    6: "💛 *Время открыть пакетик с номером 6* 💕",
    7: "💛 *Время открыть пакетик с номером 7* 💕",
    8: "💛 *Время открыть пакетик с номером 8* 💕",
    9: "💛 *Время открыть пакетик с номером 9* 💕",
    10: "💛 *Время открыть пакетик с номером 10* 💕"
}


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
            result.append(f"🧸 Обнимашки: {self.hugs} минут")
        if self.kisses > 0:
            result.append(f"💋 Поцелуи: {self.kisses} штук")
        if self.wishes > 0:
            result.append(f"🪄 Желания: {self.wishes} шт")
        return "\n".join(result) if result else "🎉 Долгов нет!"


class UserActionLog:
    """Класс для логирования действий пользователя"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.actions: List[Dict] = []

    def log_action(self, action: str, details: str, data: Optional[Dict] = None):
        """Записать действие в лог"""
        action_record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': action,
            'details': details,
            'data': data or {}
        }
        self.actions.append(action_record)

        # Также записываем в файл через логгер
        user_actions_logger.info(
            '',
            extra={
                'user_id': self.user_id,
                'action': action,
                'details': details
            }
        )

    def get_recent_actions(self, limit: int = 10) -> List[Dict]:
        """Получить последние действия"""
        return self.actions[-limit:] if self.actions else []

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'actions': self.actions
        }

    @classmethod
    def from_dict(cls, data):
        log = cls(data['user_id'])
        log.actions = data.get('actions', [])
        return log


class UserProgress:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_question = 1
        self.used_hints: Dict[int, list] = {}  # какие подсказки использованы
        self.showed_solutions: list = []  # номера вопросов, где показано решение
        self.questions_without_hints = []  # номера вопросов, пройденных без подсказок
        self.debt = UserDebt()  # Изначально долг равен 0
        self.start_time = datetime.now().isoformat()
        self.has_started_quest = False  # Флаг, начал ли пользователь квест
        self.action_log = UserActionLog(user_id)  # Лог действий пользователя

        # Логируем инициализацию прогресса
        self.action_log.log_action('INIT', 'Создан новый прогресс пользователя')

    def log_user_message(self, message: str):
        """Записать сообщение пользователя в лог"""
        self.action_log.log_action(
            'USER_MESSAGE',
            f'Пользователь отправил сообщение',
            {'message': message[:200]}  # Ограничиваем длину сообщения
        )

    def log_correct_answer(self, question_id: int):
        """Записать правильный ответ"""
        self.action_log.log_action(
            'CORRECT_ANSWER',
            f'Правильный ответ на вопрос {question_id}',
            {'question_id': question_id}
        )

    def log_wrong_answer(self, question_id: int, user_answer: str):
        """Записать неправильный ответ"""
        self.action_log.log_action(
            'WRONG_ANSWER',
            f'Неправильный ответ на вопрос {question_id}',
            {'question_id': question_id, 'user_answer': user_answer[:100]}
        )

    def log_hint_used(self, question_id: int, hint_num: int):
        """Записать использование подсказки"""
        self.action_log.log_action(
            'HINT_USED',
            f'Использована подсказка {hint_num} для вопроса {question_id}',
            {'question_id': question_id, 'hint_num': hint_num}
        )

    def log_solution_shown(self, question_id: int):
        """Записать показ решения"""
        self.action_log.log_action(
            'SOLUTION_SHOWN',
            f'Показано решение вопроса {question_id}',
            {'question_id': question_id}
        )

    def log_quest_started(self):
        """Записать начало квеста"""
        self.action_log.log_action('QUEST_STARTED', 'Пользователь начал квест')

    def log_quest_completed(self):
        """Записать завершение квеста"""
        total_completed, without_hints = self.get_stats()
        self.action_log.log_action(
            'QUEST_COMPLETED',
            'Пользователь завершил квест',
            {
                'total_completed': total_completed,
                'without_hints': without_hints,
                'debt': self.debt.to_dict()
            }
        )

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

            # Логируем использование подсказки
            self.log_hint_used(question_id, hint_num)

    def add_solution_shown(self, question_id: int):
        """Добавить просмотр решения"""
        if question_id not in self.showed_solutions:
            self.showed_solutions.append(question_id)
            # Добавляем долг за просмотр решения
            self.debt.add_wish(1)
            # Логируем показ решения
            self.log_solution_shown(question_id)

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
            'start_time': self.start_time,
            'has_started_quest': self.has_started_quest,
            'action_log': self.action_log.to_dict()
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
        progress.has_started_quest = data.get('has_started_quest', False)
        progress.action_log = UserActionLog.from_dict(
            data.get('action_log', {'user_id': data['user_id'], 'actions': []}))
        return progress


# Вопросы для квеста
QUESTIONS = [
    Question(
        id=1,
        description="ПЕРВАЯ ЗАГАДКА",
        text="*Расшифруй ответ:* \n\n`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InF1ZXN0X3VzZXJfMTIzNCIsImVtYWlsIjoicXVlc3QuZW1haWxAZXhhbXBsZS5jb20iLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTIzNDU2NzgsImlhdCI6MTcxMjM0MjA3OCwiYW5zd2VyIjoid29uZGVyZnVsIiwicmFuZG9tX251bWIiOjM3Miwic2Vzc2lvbl9pZCI6InNlc3NfYWJjZDM0NWVmMTIzIn0.7bKZoxXqprOYL6rT3JMFrwcAUR1imjX7BzXXDbRzIpo`",
        answer="wonderful",
        hint1="Ты ж программист =)",
        hint2="Кажется это какой-то токен, и ответ спрятан внутри) Ответ не на русском)",
    ),
    Question(
        id=2,
        description="ВТОРАЯ ЗАГАДКА",
        text="*Вопрос-интерактив =)*  \n\n В твоем доме спряталось *10* снеговичков! \n\nНайди их все, а когда справишься, то нужно разгадать зашифрованное слово)",
        answer="медвежонок",
        hint1="Снеговички очень маленькие и милые) \nНа их дне спрятались буквы, из которых нужно составить слово.",
        hint2="Буквы на снеговичках: В Ж Д К О Е М О Н Е. \nИ это ты!)",
    ),
    Question(
        id=3,
        description="ТРЕТЬЯ ЗАГАДКА",
        text="*Реши кроссворд)*",
        answer="наши",
        hint1="\n1. Треугольник \n2. Орфография",
        hint2="\n3. Чебурашка\n4. Исток",
        image_url="https://github.com/iukh/iukh_quest_bot/blob/main/images/%D0%BA%D1%80%D0%BE%D1%81%D1%81%D0%B2%D0%BE%D1%80%D0%B4.png?raw=true"
    ),
    Question(
        id=4,
        description="ЧЕТВЕРТАЯ ЗАГАДКА",
        text="*Расшифруй слово* \n\nПТ3ПТ1ВТ3ПТ2ВС5ПТ1 \n\n*Ключ:* месяц нашей первой встречи =)",
        answer="теплые",
        hint1="Мы встретились в январе 2023 года) \nШифр надо разбить на пары день недели и число. ",
        hint2="А - ВС1, К - ЧТ2. Шифр заменяет каждую букву на день недели месяца, согласно порядковому номеру этой буквы в алфавите. \nЛучше открыть или нарисовать календарик =)",
    ),
    Question(
        id=5,
        description="ПЯТАЯ ЗАГАДКА",
        text="*Напиши ответ на загадку:* \n\n `Rfhnbyrb ,tp 'rhfyf? ujkjcf ,tp eitq/ Jbxysq fh[bd xtkjdtrf/` \n\nP.S.: ответ во множественном числе",
        answer="воспоминания",
        hint1="Загадка написано с дефектом клавиатуры.",
        hint2="Их «перелистывают» в мыслях, а «хранят» в сердце или в голове.",
    ),
    Question(
        id=6,
        description="ШЕСТАЯ ЗАГАДКА",
        text="*А что тут написано? =)*",
        answer="согревают",
        hint1="Внешний вид букв искажен отрицательно",
        hint2="Наложи ключ на букву и убери все совпадающие линии",
        image_url="https://github.com/iukh/iukh_quest_bot/blob/main/images/negative.png?raw=true"
    ),
    Question(
        id=7,
        description="СЕДЬМАЯ ЗАГАДКА",
        text="Расшифруй ребус =)",
        answer="скучаю",
        hint1="На первой картинке нота СИ",
        hint2="На третье картинке ЮАР",
        image_url="https://github.com/iukh/iukh_quest_bot/blob/main/images/computer.png?raw=true"
    ),
    Question(
        id=8,
        description="ВОСЬМАЯ ЗАГАДКА",
        text="И снова шифр! \nЗЕФ ГТУСЁШФ \n\n Ключ: 1",
        answer="жду встречу",
        hint1="Цезарь - не салат, а шифр) Ключ - это сдвиг относительно алфавита",
        hint2="Шифр заменяет кажду букву на другую букву, находящуюся справа от нее со смещением равным значению ключа. А -> Б; Б -> В",
        image_url="https://github.com/iukh/iukh_quest_bot/blob/main/images/%D1%86%D0%B5%D0%B7%D0%B0%D1%80%D1%8C.jpg?raw=true"
    ),
    Question(
        id=9,
        description="ДЕВЯТАЯ ЗАГАДКА",
        text="Что зашифровано на картинке?)",
        answer="твой ёжик",
        hint1="Основное действие - вычитание",
        hint2="Буква получается результатом вычитания координаты по оси X и Y. Например, 52-15 = 37 = В",
        image_url="https://github.com/iukh/iukh_quest_bot/blob/main/images/%D0%B5%D0%B6%D0%B8%D0%BA.png?raw=true"
    ),
    Question(
        id=10,
        description="ДЕСЯТАЯ ЗАГАДКА",
        text="А в финале будет просто загадка, которая заставила меня саму поломать голову: \n\nЯ нечетное число. Убери одну букву и я стану четным!",
        answer="seven",
        hint1="Ответ на английском!",
        hint2="Убрать надо первую букву, а число от 1 до 10)",
    ),
]


class QuestBot:
    def __init__(self):
        self.user_progress: Dict[int, UserProgress] = {}
        self.load_progress()
        self.admin_user_id = 372495015  # ID пользователя для отправки результатов

    def escape_markdown(self, text: str) -> str:
        """Экранирует специальные символы Markdown"""
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def send_results_to_admin(self, user_progress: UserProgress, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет результаты прохождения квеста администратору"""
        try:
            total_completed, without_hints = user_progress.get_stats()

            # Экранируем текст долга
            debt_str = self.escape_markdown(str(user_progress.debt))

            # Формируем отчет с Markdown форматированием
            report = (
                f"📊 *РЕЗУЛЬТАТЫ ПРОХОЖДЕНИЯ КВЕСТА*\n\n"
                f"👤 *Пользователь:* `{user_progress.user_id}`\n"
                f"📅 *Дата начала:* `{user_progress.start_time[:19]}`\n"
                f"🎯 *Завершено:* `{total_completed}`/`{len(QUESTIONS)}`\n"
                f"✅ *Без подсказок:* `{without_hints}`\n"
                f"💡 *С подсказками:* `{total_completed - without_hints}`\n"
                f"🔴 *Решений показано:* `{len(user_progress.showed_solutions)}`\n\n"
                f"💝 *Долг:*\n`{debt_str}`"
            )

            # Отправляем отчет администратору
            await context.bot.send_message(
                chat_id=self.admin_user_id,
                text=report,
                parse_mode='MarkdownV2'
            )

            logger.info(f"Отправлены результаты пользователя {user_progress.user_id} администратору {self.admin_user_id}")

        except Exception as e:
            logger.error(f"Ошибка при отправке результатов администратору: {e}")
            # Пробуем отправить без форматирования
            try:
                simple_report = (
                    f"РЕЗУЛЬТАТЫ ПРОХОЖДЕНИЯ КВЕСТА\n\n"
                    f"Пользователь: {user_progress.user_id}\n"
                    f"Дата начала: {user_progress.start_time[:19]}\n"
                    f"Завершено: {total_completed}/{len(QUESTIONS)}\n"
                    f"Без подсказок: {without_hints}\n"
                    f"С подсказками: {total_completed - without_hints}\n"
                    f"Решений показано: {len(user_progress.showed_solutions)}\n\n"
                    f"Долг: {str(user_progress.debt)}"
                )

                await context.bot.send_message(
                    chat_id=self.admin_user_id,
                    text=simple_report
                )
            except Exception as e2:
                logger.error(f"Ошибка при отправке простого отчета: {e2}")

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
            buttons.append(
                [InlineKeyboardButton("🧸 Подсказка 1 (+5 мин обнимашек)", callback_data=f"hint_{question_id}_1")])
        if 2 not in used_hints:
            buttons.append(
                [InlineKeyboardButton("💋 Подсказка 2 (+10 поцелуев)", callback_data=f"hint_{question_id}_2")])

        # Кнопка решения (появляется только после обеих подсказок)
        if len(used_hints) >= 2 and question_id not in progress.showed_solutions:
            buttons.append([InlineKeyboardButton("🔴 Ответ (+1 желание)", callback_data=f"solution_{question_id}")])

        return InlineKeyboardMarkup(buttons) if buttons else None

    def get_question_text(self, user_id: int, question: Question) -> str:
        """Формирует текст вопроса со статистикой и использованными подсказками"""
        progress = self.get_user_progress(user_id)
        total_completed, without_hints = progress.get_stats()
        used_hints = progress.used_hints.get(question.id, [])

        text = (
            f"{question.text}\n\n"
            f"▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n\n"
        )

        # Показываем использованные подсказки
        if 1 in used_hints:
            text += f"💡 *Подсказка 1:* {question.hint1}\n"
        if 2 in used_hints:
            text += f"💡 *Подсказка 2:* {question.hint2}\n"

        if used_hints:
            text += "\n"

        text += (
            f"*Прогресс:* \n 📈 {total_completed}/{len(QUESTIONS)}\n"
        )

        debt_str = str(progress.debt)
        if debt_str != "🎉 Долгов нет!":
            text += f"\n *Текущий долг:*\n{debt_str}\n"

        return text


async def send_message(update: Update, text: str, parse_mode: str = 'Markdown', reply_markup=None,
                       image_url: Optional[str] = None):
    """Универсальная функция для отправки сообщений"""
    if image_url:
        try:
            if update.message:
                await update.message.reply_photo(photo=image_url, caption=text, parse_mode=parse_mode,
                                                 reply_markup=reply_markup)
            elif update.callback_query:
                await update.callback_query.message.reply_photo(photo=image_url, caption=text, parse_mode=parse_mode,
                                                                reply_markup=reply_markup)
            elif update.effective_message:
                await update.effective_message.reply_photo(photo=image_url, caption=text, parse_mode=parse_mode,
                                                           reply_markup=reply_markup)
            return
        except Exception as e:
            logger.error(f"Ошибка при отправке изображения: {e}")
            # Продолжаем отправку текста без изображения

    # Отправляем просто текст
    if update.message:
        return await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.callback_query:
        return await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.effective_message:
        return await update.effective_message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def send_question(update: Update, user_id: int, bot: 'QuestBot'):
    """Функция для отправки вопроса с изображением и клавиатурой"""
    question = bot.get_current_question(user_id)
    if not question:
        await send_message(update, "🎉 Квест завершен! Нажми /restart чтобы начать заново.")
        return

    text = bot.get_question_text(user_id, question)
    keyboard = bot.get_question_keyboard(user_id, question.id)

    await send_message(
        update,
        text,
        reply_markup=keyboard,
        parse_mode='Markdown',
        image_url=question.image_url
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']

    progress = bot.get_user_progress(user.id)

    # Если квест уже завершен
    if progress.current_question > len(QUESTIONS):
        await send_message(update, "🎉 Ты уже завершил квест! Нажми /restart чтобы начать заново.")
        return

    # Если пользователь еще не начинал квест
    if not progress.has_started_quest:
        welcome_text = (
            f"Привет, мой милый *{user.first_name}*! 🧡\n\n"
            f"Добро пожаловать в квест:\n"
            f"🧡 *В ожидании тепла* 🧡\n\n"
            f"Если вдруг зимним вечером тебе станет скучно, то ты можешь открыть этот квест и попробовать решить какую-нибудь загадку)\n\n"
            f"Не обещаю, что станет веселее, но это должно немного отвлечь тебя, и, надеюсь, принести немного приятных эмоций)\n\n"
            f"Всего тебя ждут *{len(QUESTIONS)}* загадок!\n\n"
            f"🎮 *Как играть:*\n"
            f"1. Отвечай на загадки, отправляя ответ в чат\n"
            f"2. Если сложно - используй подсказки (кнопки ниже)\n"
            f"3. После обеих подсказок появится кнопка 'Ответ'\n"
            f"4. Все ответы вводятся маленькими буквами\n"
            f"5. Куда присылать жалобы ты точно знаешь)\n\n"
            f"📖 *Особые правила:*\n"
            f"Если вдруг возникнут трудности, то ты можешь взять подсказку\n"
            f"• За первую подсказку: +5 минут *обнимашек* для ёжика 🧸\n"
            f"• За вторую подсказку: +10 *поцелуев* ёжика 💋\n"
            f"• За ответ (после обеих подсказок): +1 исполнение *желания* ёжика 🪄\n\n"
            f"*Готов принять вызов? =)*🪄\n\n"
        )

        # Создаем клавиатуру с кнопкой "Начать квест"
        start_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Начать квест", callback_data="start_quest")]
        ])

        await send_message(update, welcome_text, parse_mode='Markdown', reply_markup=start_keyboard)
        return

    # Если пользователь уже начал квест
    question = bot.get_current_question(user.id)

    # Показываем сообщение с номером загадки
    await send_message(
        update,
        f"❤️🧡💛️ *Загадка {question.id} из {len(QUESTIONS)}* 💛🧡❤️",
        parse_mode='Markdown'
    )

    # Небольшая пауза для эффекта
    await asyncio.sleep(0.5)

    # Показываем саму загадку
    await send_question(update, user.id, bot)


async def handle_start_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки 'Начать квест'"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    bot: QuestBot = context.bot_data['quest_bot']

    progress = bot.get_user_progress(user.id)

    # Устанавливаем флаг, что пользователь начал квест
    progress.has_started_quest = True
    progress.log_quest_started()
    bot.save_progress()

    # ВМЕСТО РЕДАКТИРОВАНИЯ СООБЩЕНИЯ - ОТПРАВЛЯЕМ НОВОЕ
    # Показываем сообщение с номером загадки как новое сообщение
    await query.message.reply_text(
        text=f"❤️🧡💛️ *Загадка 1 из {len(QUESTIONS)}* 💛🧡❤️",
        parse_mode='Markdown'
    )

    # Небольшая пауза для эффекта
    await asyncio.sleep(0.5)

    # Показываем первую загадку
    await send_question(update, user.id, bot)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (ответов на вопросов)"""
    user = update.effective_user
    message_text = update.message.text.strip().lower()
    bot: QuestBot = context.bot_data['quest_bot']

    progress = bot.get_user_progress(user.id)

    # Логируем сообщение пользователя
    progress.log_user_message(message_text)

    # Проверяем, начал ли пользователь квест
    if not progress.has_started_quest:
        await update.message.reply_text(
            "🎮 Сначала начни квест! Нажми /start чтобы начать.",
            parse_mode='Markdown'
        )
        return

    question = bot.get_current_question(user.id)

    if not question:
        await update.message.reply_text("🎉 Квест завершен! Нажми /restart чтобы начать заново.")
        return

    # Проверка ответа
    if message_text == question.answer.lower():
        # Логируем правильный ответ
        progress.log_correct_answer(question.id)

        # Отмечаем вопрос как пройденный и проверяем подсказки
        progress.mark_question_completed(question.id)

        # Получаем уникальное поздравление для этого вопроса
        congratulation_text = CONGRATULATIONS.get(question.id, "🎉 *Правильно!* Отличная работа!")

        # Добавляем статистику к поздравлению
        total_completed, without_hints = progress.get_stats()
        used_hints = len(progress.used_hints.get(question.id, []))

        stats_part = f"\n\n📈 *Статистика этой загадки:*\n"
        if used_hints == 0:
            stats_part += f"✅ *Идеально!* Без подсказок!\n"
        elif used_hints == 1:
            stats_part += f"💡 Использована 1 подсказка\n"
        else:
            stats_part += f"💡 Использовано {used_hints} подсказки\n"

        full_congratulation = f"{congratulation_text}{stats_part}"

        # Для последнего вопроса показываем финальные результаты сразу
        if question.id == len(QUESTIONS):
            # Сохраняем прогресс
            progress.current_question += 1
            progress.log_quest_completed()
            bot.save_progress()

            # Показываем поздравление
            await update.message.reply_text(full_congratulation, parse_mode='Markdown')

            # Пауза перед финальными результатами
            await asyncio.sleep(2)

            # Показываем финальные результаты
            await show_final_results(update, progress, bot, context)
            return

        # Для не-последних вопросов показываем поздравление с кнопкой "Продолжить"
        continue_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Продолжить", callback_data=f"next_{question.id}")]
        ])

        await update.message.reply_text(
            full_congratulation,
            parse_mode='Markdown',
            reply_markup=continue_keyboard
        )

    else:
        # Логируем неправильный ответ
        progress.log_wrong_answer(question.id, message_text)

        await update.message.reply_text(
            "❌ Неправильно. Попробуй еще раз! \n\n Или может стоит воспользоваться подсказкой? 😉 ")


async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки 'Продолжить' после правильного ответа"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    bot: QuestBot = context.bot_data['quest_bot']

    # Извлекаем данные из callback_data
    try:
        action, question_id_str = query.data.split('_')
        question_id = int(question_id_str)
    except ValueError:
        logger.error(f"Неверный формат callback_data: {query.data}")
        return

    progress = bot.get_user_progress(user.id)

    # Проверяем, начал ли пользователь квест
    if not progress.has_started_quest:
        await query.edit_message_text(
            text="🎮 Сначала начни квест! Нажми /start чтобы начать.",
            reply_markup=None
        )
        return

    # ВАЖНО: после правильного ответа current_question уже увеличен на 1
    # Поэтому проверяем, что question_id соответствует предыдущему вопросу
    # или что это следующий вопрос
    expected_current = question_id + 1 if action == "next" else progress.current_question

    # Если текущий вопрос не соответствует ожидаемому, все равно продолжаем
    # (это может быть из-за задержек или других проблем)

    # Увеличиваем номер текущего вопроса, если это нужно
    if progress.current_question == question_id:
        progress.current_question += 1
    elif progress.current_question < question_id:
        # Пользователь пытается перейти к вопросу, который еще не пройден
        # В этом случае просто показываем текущий вопрос
        await query.edit_message_text(
            text="Продолжай текущую загадку!",
            reply_markup=None
        )
        await send_question(update, user.id, bot)
        return

    bot.save_progress()

    # Показываем следующий вопрос
    next_question = bot.get_current_question(user.id)
    if next_question:
        # Отправляем новое сообщение с номером загадки
        await query.message.reply_text(
            text=f"❤️🧡💛️ *Загадка {next_question.id} из {len(QUESTIONS)}* 💛🧡❤️",
            parse_mode='Markdown'
        )

        await send_question(update, user.id, bot)
    else:
        # Это последний вопрос завершен - показываем финальные результаты
        progress.log_quest_completed()
        await show_final_results_from_query(query, progress, bot, context)


async def show_final_results(update, progress, bot, context):
    """Показать финальные результаты"""
    total_completed, without_hints = progress.get_stats()

    response = (
        f"🎊 *ПОЗДРАВЛЯЮ С ЗАВЕРШЕНИЕМ КВЕСТА!* 🎊\n\n"
        f"Ты успешно прошел все {len(QUESTIONS)} загадок!\n\n"
        f"📈 *Итоговая статистика:*\n"
        f"• 🎯 Пройдено заданий: {total_completed}\n"
        f"• ✅ Без подсказок: {without_hints}\n"
        f"• 💡 С подсказками: {total_completed - without_hints}\n\n"
        f"💝 *Твой долг:*\n{progress.debt}\n\n"
    )

    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        response += (
            f"🌟 *Напоминание:*\n"
            f"Все обещания нужно выполнить при первой встрече!✨\n"
        )
    else:
        response += (
            f"🏆 *ВАУ! Идеальный результат!*\n"
            f"Ты прошел весь квест без единой подсказки!\n"
        )

    response += (
        f"🧡 *Спасибо за участие!*\n"
        f"Замечательный медвежонок, теплые воспоминания о наших совместных встречах и правда согревают мое сердце даже вдалеке от тебя ❤️\n"
        f"Очень скучаю и жду нашей новой встречи ❤️\n\n"
        f"P.S.: даже если у тебя не оказалось долгов по итогу прохождения квеста, то это не повод не заообнимать и не зацеловать меня при первой встрече ❤️\n\n"
        f"Нажми /restart чтобы пройти квест еще раз!"
    )

    await send_message(update, response, parse_mode='Markdown')

    # Отправляем результаты администратору
    await bot.send_results_to_admin(progress, context)


async def show_final_results_from_query(query, progress, bot, context):
    """Показать финальные результаты из callback query"""
    total_completed, without_hints = progress.get_stats()

    response = (
        f"🎊 *ПОЗДРАВЛЯЮ С ЗАВЕРШЕНИЕМ КВЕСТА!* 🎊\n\n"
        f"Ты успешно прошел все {len(QUESTIONS)} загадок!\n\n"
        f"📈 *Итоговая статистика:*\n"
        f"• 🎯 Пройдено загадок: {total_completed}\n"
        f"• ✅ Без подсказок: {without_hints}\n"
        f"• 💡 С подсказками: {total_completed - without_hints}\n\n"
        f"💝 *Твой долг:*\n{progress.debt}\n\n"
    )

    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        response += (
            f"🌟 *Напоминание:*\n"
            f"Все обещания нужно выполнить при первой встрече!\n"
            f"Это сделает вашу встречу волшебной! ✨\n\n"
        )
    else:
        response += (
            f"🏆 *ВАУ! Идеальный результат!*\n"
            f"Ты прошел весь квест без единой подсказки!\n"
            f"Ты заслужил особый сюрприз! 🎁\n\n"
        )

    response += (
        f"🧡 *Спасибо за участие!*\n"
        f"Пусть в твоей жизни всегда будет тепло и любовь! ❤️\n\n"
        f"Нажми /restart чтобы пройти квест еще раз!"
    )

    await query.message.reply_text(response, parse_mode='Markdown')

    # Отправляем результаты администратору
    await bot.send_results_to_admin(progress, context)


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

    # Проверяем, начал ли пользователь квест
    if not progress.has_started_quest:
        await query.edit_message_text(
            text="🎮 Сначала начни квест! Нажми /start чтобы начать.",
            reply_markup=None
        )
        return

    # Проверяем, что пользователь на текущем вопросе
    if progress.current_question != question_id:
        await query.edit_message_text(
            text="Эта загадка уже пройдена. Продолжай текущую!",
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
        await query.edit_message_caption(
            caption=text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        # Если сообщение без фото или другая ошибка
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e2:
            logger.error(f"Ошибка при обновлении сообщения: {e2}")
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

    # Проверяем, начал ли пользователь квест
    if not progress.has_started_quest:
        await query.edit_message_text(
            text="🎮 Сначала начни квест! Нажми /start чтобы начать.",
            reply_markup=None
        )
        return

    # Проверяем, что пользователь на текущем вопросе
    if progress.current_question != question_id:
        await query.edit_message_text(
            text="Эта загадка уже пройдена. Продолжай текущую)!",
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

    # Получаем уникальное ободряющее сообщение для этого вопроса
    encouragement_text = ENCOURAGEMENTS.get(question_id, "В любом случае, ты молодец!")

    # Для последнего вопроса показываем финальные результаты
    if question_id == len(QUESTIONS):
        progress.current_question += 1
        progress.log_quest_completed()

        # Формируем сообщение с решением
        text = bot.get_question_text(user.id, question)
        text += f"\n*Ответ:* \n🔴 {question.answer}"

        # Создаем сообщение о наказании с уникальным ободряющим текстом
        penalty_text = (
            f"🪄 *Уи, теперь ты должен желание!*\n\n"
            f"💌 *Что это значит:*\n"
            f"Ёжик может загадать одно желание,\n"
            f"которое тебе нужно будет выполнить! ❤️\n\n"
            f"💔 *Но это совсем не повод расстраиваться!*\n"
            f"Задачки неидеальны, и если не удалось найти решение, то всего скорее они просто некачественно составлены)\n"
            f"{encouragement_text}"
        )

        # Обновляем сообщение с вопросом и решением
        try:
            await query.edit_message_caption(
                caption=text,
                reply_markup=None,
                parse_mode='Markdown'
            )
        except:
            await query.edit_message_text(
                text=text,
                reply_markup=None,
                parse_mode='Markdown'
            )

        # Отправляем сообщение о наказании
        await query.message.reply_text(penalty_text, parse_mode='Markdown')

        # Пауза перед финальными результатами
        await asyncio.sleep(2)

        # Показываем финальные результаты
        await show_final_results_from_query(query, progress, bot, context)
        bot.save_progress()
        return

    # Для не-последних вопросов показываем решение с кнопкой "Продолжить"
    progress.current_question += 1

    # Формируем сообщение с решением
    text = bot.get_question_text(user.id, question)
    text += f"\n🔴 *Ответ:* {question.answer}"

    # Создаем сообщение о наказании с уникальным ободряющим текстом
    penalty_text = (
        f"🪄 *Уи, теперь ты должен одно желание!*\n\n"
        f"💌 *Что это значит:*\n"
        f"Ёжик может загадать одно желание,\n"
        f"которое тебе нужно будет выполнить! ❤️\n\n"
        f"💔 *Это не повод расстраиваться!*\n"
        f"{encouragement_text}\n\n"
        f"Нажми 'Продолжить' для перехода к следующей загадке:"
    )

    continue_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Продолжить", callback_data=f"next_{question_id}")]
    ])

    # Обновляем сообщение с вопросом и решением
    try:
        await query.edit_message_caption(
            caption=text,
            reply_markup=None,
            parse_mode='Markdown'
        )
    except:
        await query.edit_message_text(
            text=text,
            reply_markup=None,
            parse_mode='Markdown'
        )

    # Отправляем сообщение о наказании с кнопкой продолжить
    await query.message.reply_text(penalty_text, parse_mode='Markdown', reply_markup=continue_keyboard)

    bot.save_progress()


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс прогресса и начало заново"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']

    # Логируем сброс прогресса
    old_progress = bot.get_user_progress(user.id)
    user_actions_logger.info(
        'RESTART',
        extra={
            'user_id': user.id,
            'action': 'RESTART',
            'details': f'Сброс прогресса. Старый прогресс: {old_progress.current_question} вопрос'
        }
    )

    # Сбрасываем прогресс
    bot.user_progress[user.id] = UserProgress(user.id)
    bot.save_progress()

    response_text = (
        "🔄 Прогресс сброшен! Все долги обнулены.\n"
        "Нажми /start чтобы начать квест заново!"
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
            f"*Квест завершен!*\n\n"
            f"📈 *Итоговая статистика:*\n"
            f"• 🎯 Пройдено заданий: {total_completed}/{len(QUESTIONS)}\n"
            f"• ✅ Без подсказок: {without_hints}\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"💝 *Твой долг тепла:*\n{progress.debt}\n\n"
        )

        if progress.debt.hugs == 0 and progress.debt.kisses == 0 and progress.debt.wishes == 0:
            stats_text += "🏆 *Идеальный результат!* Ты прошел квест без долгов!\n\n"

        stats_text += "Нажми /restart чтобы начать заново."
    else:
        question = bot.get_current_question(user.id)
        current_hints = len(progress.used_hints.get(progress.current_question, []))

        stats_text = (
            f"*Квест: В ожидании тепла*\n\n"
            f"📈 *Статистика:*\n"
            f"• 📈 Прогресс: {total_completed}/{len(QUESTIONS)}\n"
            f"• ✅ Без подсказок: {without_hints} загадок\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"🎯 *Текущий загадка:* {progress.current_question}\n"
            f"🔍 Использовано подсказок: {current_hints}/2\n\n"
            f"💝 *Твой долг:*\n{progress.debt}\n\n"
        )

        if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
            stats_text += (
                "🌟 *Напоминание:*\n"
                "Каждая подсказка и ответ - это обещание тепла и нежности!\n"
                "Выполни все при первой встрече! ✨\n\n"
            )

        stats_text += f" *Текущая загадка:* {question.text[:60]}..."

    await send_message(update, stats_text, parse_mode='Markdown')


async def debt_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о долгах"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']

    progress = bot.get_user_progress(user.id)
    total_completed, without_hints = progress.get_stats()

    debt_text = (
        f"💝 *Твой долг тепла:*\n\n"
        f"{progress.debt}\n\n"
    )

    if progress.debt.hugs > 0 or progress.debt.kisses > 0 or progress.debt.wishes > 0:
        debt_text += (
            f"📊 *Контекст:*\n"
            f"• 🎯 Пройдено загадок: {total_completed}\n"
            f"• ✅ Без подсказок: {without_hints}\n"
            f"• 💡 С подсказками: {total_completed - without_hints}\n"
            f"• 🔴 Показано решений: {len(progress.showed_solutions)}\n\n"
            f"🌟 *Важно:*\n"
            f"Все обещания нужно выполнить при первой встрече!💕\n"
        )
    else:
        debt_text += (
            f"🎉 *Ура! У тебя нет долгов!*\n"
            f"Ты молодец! Продолжай в том же духе!\n\n"
            f"📈 Статистика: {without_hints}/{total_completed} без подсказок\n\n"
        )

    await send_message(update, debt_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь по командам"""
    help_text = (
        "🧡 *Квест: В ожидании тепла*\n\n"
        "📋 *Доступные команды:*\n\n"
        "/start - Начать или продолжить квест\n"
        "/restart - Начать квест заново (обнуляет долги)\n"
        "/stats - Подробная статистика\n"
        "/debt - Показать текущий долг\n"
        "/help - Показать это сообщение\n\n"
        "📖 *Особые правила квеста:*\n"
        "1. Отвечай на загадки, отправляя ответы текстом\n"
        "2. Если нужна помощь - используй подсказки:\n"
        "   • 🧸 Первая подсказка: +5 минут обнимашек для ёжика\n"
        "   • 💋 Вторая подсказка: +10 поцелуев для ёжика\n"
        "3. После обеих подсказок появляется кнопка:\n"
        "   • 🔴 Ответ: +1 исполнение желания ёжика\n"
        "4. Чем меньше подсказок - тем лучше результат!\n"
        "5. Все долги нужно выполнить при первой встрече! ⏰\n\n"
        "📝 *Важно:*\n"
        "• Ответы вводи строчными буквами\n"
        "• Без лишних символов и пробелов\n"
        "• Прогресс сохраняется автоматически\n\n"
        "🧡 *Скучаю по тебе и жду встречи!* 🧡"
    )

    await send_message(update, help_text, parse_mode='Markdown')


async def clear_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отметки выполнения долгов"""
    user = update.effective_user
    bot: QuestBot = context.bot_data['quest_bot']

    progress = bot.get_user_progress(user.id)
    old_debt = str(progress.debt)

    # Логируем очистку долга
    user_actions_logger.info(
        'CLEAR_DEBT',
        extra={
            'user_id': user.id,
            'action': 'CLEAR_DEBT',
            'details': f'Очистка долга. Было: {old_debt}'
        }
    )

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


async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения логов (только для администратора)"""
    user = update.effective_user

    # Проверяем, является ли пользователь администратором
    if user.id != 372495015:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    try:
        # Читаем последние 20 строк из лог-файла
        with open('user_actions.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-20:] if len(lines) > 20 else lines

        logs_text = "📋 *Последние 20 действий из лога:*\n\n"
        for line in last_lines:
            logs_text += f"`{line.strip()}`\n"

        await update.message.reply_text(logs_text, parse_mode='Markdown')

    except FileNotFoundError:
        await update.message.reply_text("📭 Лог-файл не найден.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при чтении логов: {e}")


async def get_user_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить логи конкретного пользователя (только для администратора)"""
    user = update.effective_user

    # Проверяем, является ли пользователь администратором
    if user.id != 372495015:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    # Проверяем, указан ли ID пользователя
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя: /user_logs <user_id>")
        return

    try:
        user_id = int(context.args[0])
        bot: QuestBot = context.bot_data['quest_bot']

        if user_id in bot.user_progress:
            progress = bot.user_progress[user_id]
            recent_actions = progress.action_log.get_recent_actions(15)

            if recent_actions:
                logs_text = f"📋 *Последние 15 действий пользователя {user_id}:*\n\n"
                for action in recent_actions:
                    timestamp = action['timestamp'][:19].replace('T', ' ')
                    logs_text += f"⏰ *{timestamp}*\n"
                    logs_text += f"🔹 *Действие:* {action['action']}\n"
                    logs_text += f"📝 *Детали:* {action['details']}\n"
                    if action.get('data'):
                        logs_text += f"📊 *Данные:* {action['data']}\n"
                    logs_text += "━━━━━━━━━━━━━━━━━━━━\n"

                # Разбиваем на части, если сообщение слишком длинное
                if len(logs_text) > 4000:
                    parts = [logs_text[i:i + 4000] for i in range(0, len(logs_text), 4000)]
                    for part in parts:
                        await update.message.reply_text(part, parse_mode='Markdown')
                        await asyncio.sleep(0.5)
                else:
                    await update.message.reply_text(logs_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"📭 У пользователя {user_id} нет записей в логе.")
        else:
            await update.message.reply_text(f"❌ Пользователь {user_id} не найден.")

    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


def main():
    """Запуск бота"""
    # Токен вашего бота
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")

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

    # Команды для администратора
    application.add_handler(CommandHandler("logs", get_logs))
    application.add_handler(CommandHandler("user_logs", get_user_logs))

    # Обработчик кнопки "Начать квест"
    application.add_handler(CallbackQueryHandler(handle_start_quest, pattern=r"^start_quest$"))

    # Обработчик подсказок
    application.add_handler(CallbackQueryHandler(handle_hint, pattern=r"^hint_"))

    # Обработчик решений
    application.add_handler(CallbackQueryHandler(handle_solution, pattern=r"^solution_"))

    # Обработчик кнопки "Продолжить" (обрабатывает как next_ так и continue_ для обратной совместимости)
    application.add_handler(CallbackQueryHandler(handle_continue, pattern=r"^(next|continue)_"))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    logger.info("🧡 Квест-бот 'В ожидании тепла' запущен...")
    logger.info(f"📊 Логи действий будут сохраняться в user_actions.log")
    logger.info(f"📨 Результаты будут отправляться пользователю {quest_bot.admin_user_id}")
    application.run_polling()


if __name__ == '__main__':
    main()