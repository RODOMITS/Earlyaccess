import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

BotToken = "8631154236:AAEWh1ViGH_54cXq8I7I7EdBZvTYYN8fBRY"
ChannelId = -1003326105559

TelegramBot = Bot(token=BotToken)
BotStorage = MemoryStorage()
BotDispatcher = Dispatcher(TelegramBot, storage=BotStorage)
logging.basicConfig(level=logging.INFO)

# Локальная база данных в памяти
UsersDatabase = {}
EarlyAccessList = {}

class RegistrationStates(StatesGroup):
    WaitingForRobloxNickname = State()

async def CheckChannelSubscription(UserId: int) -> bool:
    try:
        ChatMember = await TelegramBot.get_chat_member(chat_id=ChannelId, user_id=UserId)
        return ChatMember.status in ["member", "administrator", "creator"]
    except Exception:
        return False

@BotDispatcher.message_handler(commands=["start"], state="*")
async def HandleStartCommand(Message: types.Message):
    UserId = Message.from_user.id
    CommandArgs = Message.get_args()
    
    if UserId not in UsersDatabase:
        ReferrerId = None
        if CommandArgs and CommandArgs.isdigit() and int(CommandArgs) != UserId:
            ReferrerId = int(CommandArgs)
            
        UsersDatabase[UserId] = {
            "ReferrerId": ReferrerId,
            "InvitedCount": 0,
            "RobloxNickname": None,
            "RewardReceived": False
        }
        
        if ReferrerId:
            await Message.answer("Привет! Ты перешел по ссылке друга. Подпишись на канал и нажми проверку ниже!")
            
    MenuKeyboard = types.InlineKeyboardMarkup(row_width=1)
    LinkButton = types.InlineKeyboardButton("🔗 Получить мою ссылку", callback_data="GetInviteLink")
    CheckButton = types.InlineKeyboardButton("✅ Проверить моих друзей", callback_data="CheckReferrals")
    MenuKeyboard.add(LinkButton, CheckButton)
    
    await Message.answer("Добро пожаловать! Пригласи 2 друзей в канал и получи ранний доступ к игре «Вырасти Русский Сад»!", reply_markup=MenuKeyboard)

@BotDispatcher.callback_query_handler(lambda Callback: Callback.data == "GetInviteLink", state="*")
async def HandleGetLink(CallbackQuery: types.CallbackQuery):
    UserId = CallbackQuery.from_user.id
    BotInformation = await TelegramBot.get_me()
    InviteLink = f"https://t.me/{BotInformation.username}?start={UserId}"
    
    await TelegramBot.send_message(UserId, f"Твоя ссылка для приглашения друзей:\n`{InviteLink}`", parse_mode="Markdown")
    await CallbackQuery.answer()

@BotDispatcher.callback_query_handler(lambda Callback: Callback.data == "CheckReferrals", state="*")
async def HandleCheckReferrals(CallbackQuery: types.CallbackQuery, State: FSMContext):
    UserId = CallbackQuery.from_user.id
    IsSubscribed = await CheckChannelSubscription(UserId)
    
    CurrentUserData = UsersDatabase.get(UserId)
    
    if CurrentUserData and CurrentUserData.get("ReferrerId") and IsSubscribed:
        ParentId = CurrentUserData["ReferrerId"]
        ParentData = UsersDatabase.get(ParentId)
        
        if ParentData:
            ParentData["InvitedCount"] += 1
            try:
                await TelegramBot.send_message(ParentId, "🎉 По твоей ссылке зашел новый подписчик!")
            except Exception:
                pass
                
        CurrentUserData["ReferrerId"] = None

    InvitedFriendsCount = CurrentUserData.get("InvitedCount", 0) if CurrentUserData else 0
    HasReward = CurrentUserData.get("RewardReceived", False) if CurrentUserData else False
    
    if InvitedFriendsCount >= 2 and not HasReward:
        await TelegramBot.send_message(UserId, "🔥 Отлично! Ты пригласил 2 друзей. Теперь напиши свой ник в Roblox для выдачи раннего доступа:")
        await RegistrationStates.WaitingForRobloxNickname.set()
    elif HasReward:
        SavedNickname = CurrentUserData.get("RobloxNickname", "")
        await TelegramBot.send_message(UserId, f"Ты уже активировал доступ для аккаунта: {SavedNickname}")
    else:
        await TelegramBot.send_message(UserId, f"У тебя приглашено: {InvitedFriendsCount}/2 друзей. Они должны запустить бота и подписаться на канал!")
        
    await CallbackQuery.answer()

@BotDispatcher.message_handler(state=RegistrationStates.WaitingForRobloxNickname, content_types=types.ContentTypes.TEXT)
async def HandleRobloxNicknameInput(Message: types.Message, State: FSMContext):
    RobloxNickname = Message.text.strip()
    UserId = Message.from_user.id
    
    if UserId in UsersDatabase:
        UsersDatabase[UserId]["RobloxNickname"] = RobloxNickname
        UsersDatabase[UserId]["RewardReceived"] = True
    
    EarlyAccessList[RobloxNickname] = True
    
    await State.finish()
    await Message.answer(f"🎉 Супер! Твой ник *{RobloxNickname}* успешно добавлен в белый список раннего доступа. Ты сможешь поиграть в игру на два часа раньше! (26 июня 16:00 по мск)", parse_mode="Markdown")

if __name__ == "__main__":
    executor.start_polling(BotDispatcher, skip_updates=True)
