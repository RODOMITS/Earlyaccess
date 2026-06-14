import logging
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

BotToken = "8631154236:AAEWh1ViGH_54cXq8I7I7EdBZvTYYN8fBRY"
ChannelId = -1003326105559

FirebaseCredentialPath = "key.json"
FirebaseDatabaseUrl = "https://earlyaccess-f2d4b-default-rtdb.firebaseio.com/"


AppCredentials = credentials.Certificate(FirebaseCredentialPath)
firebase_admin.initialize_app(AppCredentials, {
    "databaseURL": FirebaseDatabaseUrl
})

TelegramBot = Bot(token=BotToken)
BotStorage = MemoryStorage()
BotDispatcher = Dispatcher(TelegramBot, storage=BotStorage)
logging.basicConfig(level=logging.INFO)

class RegistrationStates(StatesGroup):
    WaitingForRobloxNickname = State()

async def CheckChannelSubscription(UserId: int) -> bool:
    try:
        ChatMember = await TelegramBot.get_chat_member(chat_id=ChannelId, user_id=UserId)
        return ChatMember.status in ["member", "administrator", "creator"]
    except Exception:
        return False

@BotDispatcher.message_handler(commands=["start"], state="*")
async def HandleStartCommand(Message: types.Message, State: FSMContext):
    await State.finish()
    UserId = Message.from_user.id
    CommandArgs = Message.get_args()
    
    UserReference = db.reference(f"Users/{UserId}")
    UserData = UserReference.get()
    
    if not UserData:
        ReferrerId = None
        if CommandArgs and CommandArgs.isdigit() and int(CommandArgs) != UserId:
            ReferrerId = int(CommandArgs)
            
        UserReference.set({
            "ReferrerId": ReferrerId,
            "InvitedCount": 0,
            "RobloxNickname": None,
            "RewardReceived": False
        })
        
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
    
    CurrentUserReference = db.reference(f"Users/{UserId}")
    CurrentUserData = CurrentUserReference.get()
    
    if CurrentUserData and CurrentUserData.get("ReferrerId") and IsSubscribed:
        ParentId = CurrentUserData["ReferrerId"]
        ParentReference = db.reference(f"Users/{ParentId}")
        ParentData = ParentReference.get()
        
        if ParentData:
            NewCount = ParentData.get("InvitedCount", 0) + 1
            ParentReference.update({"InvitedCount": NewCount})
            try:
                await TelegramBot.send_message(ParentId, "🎉 По твоей ссылке зашел новый подписчик!")
            except Exception:
                pass
                
        CurrentUserReference.update({"ReferrerId": None})
        CurrentUserData = CurrentUserReference.get()

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
    
    UserReference = db.reference(f"Users/{UserId}")
    UserReference.update({
        "RobloxNickname": RobloxNickname,
        "RewardReceived": True
    })
    
    NicknameReference = db.reference(f"EarlyAccessList/{RobloxNickname}")
    NicknameReference.set(True)
    
    await State.finish()
    await Message.answer(f"🎉 Супер! Твой ник *{RobloxNickname}* успешно добавлен в белый список раннего доступа. Ты сможешь поиграть в игру на два часа раньше! (26 июня 16:00 по мск)", parse_mode="Markdown")

if __name__ == "__main__":
    executor.start_polling(BotDispatcher, skip_updates=True)
