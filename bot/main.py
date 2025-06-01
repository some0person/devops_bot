import re
import logging
import psycopg
import paramiko

from os import remove, environ
from typing import Final
from datetime import datetime
from dotenv import dotenv_values

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters


def sshConnection(cmd: str,) -> tuple[paramiko.ChannelStdinFile, paramiko.ChannelFile, paramiko.ChannelStderrFile]:
    global env
    
    with paramiko.SSHClient() as sshClient:
        sshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        sshClient.connect(hostname=env["RM_HOST"], username=env["RM_USER"], password=env["RM_PASSWORD"], port=env["RM_PORT"])

        logging.info(f"Произведено подключение по SSH к {env["RM_USER"]}@{env["RM_HOST"]}:{env["RM_PORT"]}")
        
        stdin, stdout, stderr = sshClient.exec_command(cmd)
        logging.info(f"Выполнена команда {cmd} по SSH на {env["RM_HOST"]}:{env["RM_PORT"]}")

        stdout = str(stdout.read()).replace('\\n', '\n').replace('\\t', '\t')[2:-1]
        stderr = str(stderr.read()).replace('\\n', '\n').replace('\\t', '\t')[2:-1]

    return stdin, stdout, stderr


async def startCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(f'Привет {user.full_name}!')
    logging.info(f"Пользователь ID={user.id} использовал команду /start")


async def helpCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Help!')
    logging.info(f"Пользователь ID={update.effective_user.id} использовал команду /help")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    logging.info(f"Ответ пользователю ID={update.effective_user.id} его же сообщением")


async def writePhoneNumbers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int]:
    user_input = update.message.text

    if user_input.lower() == "нет":
        await update.message.reply_text("Хорошо, ничего не записано")
        return ConversationHandler.END

    try:
        with psycopg.connect(dbname=env["DB_DATABASE"],
                            user=env["DB_USER"],
                            password=env["DB_PASSWORD"],
                            host=env["DB_HOST"],
                            port=env["DB_PORT"]) as conn:
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO phone_nums VALUES " + ", ".join([f'(DEFAULT, \'{phone_num}\')' for phone_num in context.user_data["phone_nums"]]))
                conn.commit()

    except Exception as err:
        logging.error(f"Произошла ошибка при добавлении телефонных номеров в базу данных: {err}")
        await update.message.reply_text("Произошла непредвиденная ошибка при записи телефонных номеров. Пожалуйста, обратитесь к администратору")
        return ConversationHandler.END
    
    await update.message.reply_text("Телефонные номера успешно записаны в базу данных")
    return ConversationHandler.END


async def findPhoneNumbers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int | str]:
    user_input = update.message.text  # Получение текста от пользователя

    # Все нужные форматы номеров
    phoneNumRegex = (
        re.compile(r'(?:\+7|8)\d{10}'),  # <+7/8>XXXXXXXXXX
        re.compile(r'(?:\+7|8)\(\d{3}\)\d{7}'),  # <+7/8>(XXX)XXXXXXX
        re.compile(r'(?:\+7|8)\s\d{3}\s\d{3}\s\d{2}\s\d{2}'),  # <+7/8> XXX XXX XX XX
        re.compile(r'(?:\+7|8)\s\(\d{3}\)\s\d{3}\s\d{2}\s\d{2}'),  # <+7/8> (XXX) XXX XX XX
        re.compile(r'(?:\+7|8)-\d{3}-\d{3}-\d{2}-\d{2}')  # <+7/8>-XXX-XXX-XX-XX
    )

    logging.info(f"Проверка сообщения от пользователя ID={update.effective_user.id} на наличие телефонных номеров...")
    phoneNumberList = []
    for regex in phoneNumRegex:
        phoneNumberList.extend(regex.findall(user_input))   # Поиск номеров из текста

    if not phoneNumberList:  # Обработка случая, когда номеров нет
        logging.warning(f"Телефонные номера в сообщении пользователя ID={update.effective_user.id} не были найдены")
        await update.message.reply_text('Телефонные номера не найдены')
        return ConversationHandler.END

    context.user_data["phone_nums"] = phoneNumberList  # Запись номеров в поьзовательский словарь для передачи между ConversationHandler'ами

    # Формирование результата
    phoneNumbers = "\n".join(f"{i}. {number}" for i, number in enumerate(phoneNumberList, start=1))
    
    logging.info(f"В сообщении пользователя ID={update.effective_user.id} телефонных номеров: {len(phoneNumberList)}")
    await update.message.reply_text(phoneNumbers)  # Отправление сформированного сообщения пользователю

    await update.message.reply_text("Записать в базу данных? [Да/Нет]")
    return 'writePhoneNumbers'


async def findPhoneNumbersCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[str]:
    logging.info(f"Пользователь ID={update.effective_user.id} использовал команду /find_phone_number")
    await update.message.reply_text('Введите текст для поиска телефонных номеров:')
    return 'findPhoneNumbers'


async def writeEmailAddresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int]:
    user_input = update.message.text

    if user_input.lower() == "нет":
        await update.message.reply_text("Хорошо, ничего не записано")
        return ConversationHandler.END

    try:
        with psycopg.connect(dbname=env["DB_DATABASE"],
                            user=env["DB_USER"],
                            password=env["DB_PASSWORD"],
                            host=env["DB_HOST"],
                            port=env["DB_PORT"]) as conn:
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO emails VALUES " + ", ".join([f'(DEFAULT, \'{email}\')' for email in context.user_data["emails"]]))
                conn.commit()

    except Exception as err:
        logging.error(f"Произошла ошибка при добавлении email адресов в базу данных: {err}")
        await update.message.reply_text("Произошла непредвиденная ошибка при записи email адресов. Пожалуйста, обратитесь к администратору")
        return ConversationHandler.END
    
    await update.message.reply_text("Email адресы успешно записаны в базу данных")
    return ConversationHandler.END


async def findEmailAddresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int | str]:
    user_input = update.message.text  # Получение текста от пользователя

    emailAddrRegex = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')  # Все нужные форматы адресов

    logging.info(f"Проверка сообщения от пользователя ID={update.effective_user.id} на наличие email адресов...")
    emailAddressesList = emailAddrRegex.findall(user_input)  # Поиск адресов из текста
    context.user_data["emails"] = emailAddressesList  # Запись адресов в поьзовательский словарь для передачи между ConversationHandler'ами

    if not emailAddressesList:  # Обработка случая, когда номеров нет
        logging.warning(f"Email адреса в сообщении пользователя ID={update.effective_user.id} не были найдены")
        await update.message.reply_text('Электронные почтовые адреса не найдены')
        return ConversationHandler.END
    
    # Формирование результата
    emailAddresses = "\n".join(f"{i}. {address}" for i, address in enumerate(emailAddressesList, start=1))
    
    logging.info(f"В сообщении пользователя ID={update.effective_user.id} email адресов: {len(emailAddressesList)}")
    await update.message.reply_text(emailAddresses)  # Отправление сформированного сообщения пользователю

    await update.message.reply_text("Записать в базу данных? [Да/Нет]")
    return 'writeEmailAddresses'


async def findEmailAddressesCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[str]:
    logging.info(f"Пользователь ID={update.effective_user.id} использовал команду /find_email")
    await update.message.reply_text('Введите текст для поиска адресов электронной почты:')
    return 'findEmailAddresses'


async def verifyPassword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int]:
    user_input = update.message.text  # Получение текста от пользователя

    passwordRegex = re.compile(r'(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()]).{8,}')
    
    logging.info(f"Проверка надёжности пароля в сообщении пользователя ID={update.effective_user.id}...")
    if passwordRegex.findall(user_input):
        await update.message.reply_text('Пароль сложный')
    else:
        await update.message.reply_text('Пароль простой')

    return ConversationHandler.END


async def verifyPasswordCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[str]:
    logging.info(f"Пользователь ID={update.effective_user.id} использовал команду /verify_password")
    await update.message.reply_text('Введите пароль для проверки его надёжности:')
    return 'verifyPassword'


async def getReleaseCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("lsb_release -a")
    await update.message.reply_text(stdout)


async def getUnameCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("uname -mnv")
    await update.message.reply_text(stdout)


async def getUptimeCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("uptime -p")
    await update.message.reply_text(stdout)


async def getDfCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("df -hT")
    await update.message.reply_text(stdout)


async def getFreeCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("free -ht")
    await update.message.reply_text(stdout)


async def getMpstatCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, stderr = sshConnection("mpstat")
    await update.message.reply_text(stdout + stderr)


async def getWCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("w")
    await update.message.reply_text(stdout)


async def getAuthsCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("last -10R tty{1..9}")
    await update.message.reply_text(stdout)


async def getCriticalCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("journalctl --no-pager -q -p crit -n 5")
    await update.message.reply_text(stdout)


async def getPsCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("ps au")
    await update.message.reply_text(stdout)


async def getSsCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("ss -tulpn")
    await update.message.reply_text(stdout)


async def getPackageInfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int]:
    user_input = update.message.text  # Получение текста от пользователя
    packageNameRegex = re.compile(r"[a-z0-9.+-]*")

    if not packageNameRegex.fullmatch(user_input):
        logging.warning(f"Пользователь ID={update.effective_user.id} ввёл некорректное имя пакета")
        await update.message.reply_text("Некорректное имя пакета! Убедитесь, что оно состоит ТОЛЬКО из: [a-z0-9.+-]")
        return ConversationHandler.END

    _, stdout, _ = sshConnection(f"apt show {user_input}")
    if stdout:
        await update.message.reply_text(stdout)
    else:
        await update.message.reply_text("Пакет не найден!")

    return ConversationHandler.END


async def getAptList(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[int|str]:
    user_input = update.message.text  # Получение текста от пользователя

    if user_input == "1":
        _, stdout, _ = sshConnection("apt list")
        filename = f"apt list {datetime.now().timestamp()}.txt"

        with open(filename, "w") as file:
            file.write(stdout)
        
        with open(filename, "r") as file:
            message = "Список пакетов отправлен текстовым файлом, так как он слишком большой"
            await update.message.reply_document(document=file, caption=message)
        
        remove(filename)

        return ConversationHandler.END
    
    elif user_input == "2":
        await update.message.reply_text("Введите название пакета, о котором хотите получить информацию:")
        return 'getPackageInfo'


async def getAptListCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Final[str]:
    message = "Какую информацию Вы хотите получить? [1|2]\n\n1. Вывод всех пакетов;\n2. Поиск информации о пакете."
    await update.message.reply_text(message)
    return 'getAptList'


async def getServicesCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, stdout, _ = sshConnection("systemctl --no-pager --state running list-units *.service")

    filename = f"running services {datetime.now().timestamp()}.txt"

    with open(filename, "w") as file:
        file.write(stdout)
    
    with open(filename, "r") as file:
        message = "Список пакетов отправлен текстовым файлом, так как он слишком большой"
        await update.message.reply_document(document=file, caption=message)
    
    remove(filename)


async def getReplLogsCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global env

    with psycopg.connect(user=env["DB_USER"],
                         password=env["DB_PASSWORD"],
                         host=env["DB_HOST"],
                         port=env["DB_PORT"],
                         dbname=env["DB_DATABASE"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_current_logfile()")
            currentLogFile = cur.fetchone()[0]
            cur.execute(f"SELECT pg_read_file('{currentLogFile}')")
            replLogs = '\n'.join(filter(lambda x: env["DB_REPL_USER"] in x, cur.fetchone()[0].split('\n')))
    
    filename = currentLogFile.split("/")[-1]

    with open(filename, "w") as file:
        file.write(replLogs)

    with open(filename, "r") as file:
        message = "Логи репликации отправлены текстовым файлом, так как они слишком большие"
        await update.message.reply_document(document=file, caption=message)
    
    remove(filename)


async def getEmailsCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global env
    
    with psycopg.connect(dbname=env["DB_DATABASE"],
                         user=env["DB_USER"],
                         password=env["DB_PASSWORD"],
                         host=env["DB_HOST"],
                         port=env["DB_PORT"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM emails")
            emails = cur.fetchall()
            if emails:
                await update.message.reply_text("\n".join([". ".join(map(str, email)) for email in emails]))
            else:
                await update.message.reply_text("Список email-адресов пуст")


async def getPhoneNumbersCommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global env
    
    with psycopg.connect(dbname=env["DB_DATABASE"],
                         user=env["DB_USER"],
                         password=env["DB_PASSWORD"],
                         host=env["DB_HOST"],
                         port=env["DB_PORT"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM phone_nums")
            phone_nums = cur.fetchall()
            if phone_nums:
                await update.message.reply_text("\n".join([". ".join(map(str, phone_num)) for phone_num in phone_nums]))
            else:
                await update.message.reply_text("Список телефонных номеров пуст")


def main() -> None:
    logging.basicConfig(filename='bot.log', level=logging.DEBUG, format=' %(asctime)s - %(levelname)s - %(message)s', encoding="utf-8")
    
    global env
    env = environ
    logging.info("Загружены переменные окружения")

    app = ApplicationBuilder().token(env["TOKEN"]).build()
    
    convHandlerFindPhoneNumbers = ConversationHandler(
        entry_points=[CommandHandler('find_phone_number', findPhoneNumbersCommand)],
        states={
            'findPhoneNumbers': [MessageHandler(filters.TEXT & ~ filters.COMMAND, findPhoneNumbers)],
            'writePhoneNumbers': [MessageHandler(filters.TEXT & ~ filters.COMMAND, writePhoneNumbers)],
        },
        fallbacks=[]
    )

    convHandlerFindEmailAddresses = ConversationHandler(
        entry_points=[CommandHandler('find_email', findEmailAddressesCommand)],
        states={
            'findEmailAddresses': [MessageHandler(filters.TEXT & ~ filters.COMMAND, findEmailAddresses)],
            'writeEmailAddresses': [MessageHandler(filters.TEXT & ~ filters.COMMAND, writeEmailAddresses)],
        },
        fallbacks=[]
    )

    convHandlerVerifyPassword = ConversationHandler(
        entry_points=[CommandHandler('verify_password', verifyPasswordCommand)],
        states={
            'verifyPassword': [MessageHandler(filters.TEXT & ~ filters.COMMAND, verifyPassword)],
        },
        fallbacks=[]
    )

    convHandlerGetAptList = ConversationHandler(
        entry_points=[CommandHandler('get_apt_list', getAptListCommand)],
        states={
            'getAptList': [MessageHandler(filters.TEXT & ~ filters.COMMAND, getAptList)],
            'getPackageInfo': [MessageHandler(filters.TEXT & ~ filters.COMMAND, getPackageInfo)],
        },
        fallbacks=[]
    )

    # Обработчики команд
    app.add_handler(CommandHandler("start", startCommand))
    app.add_handler(CommandHandler("help", helpCommand))
    app.add_handler(CommandHandler("get_release", getReleaseCommand))
    app.add_handler(CommandHandler("get_uname", getUnameCommand))
    app.add_handler(CommandHandler("get_uptime", getUptimeCommand))
    app.add_handler(CommandHandler("get_df", getDfCommand))
    app.add_handler(CommandHandler("get_free", getFreeCommand))
    app.add_handler(CommandHandler("get_mpstat", getMpstatCommand))
    app.add_handler(CommandHandler("get_w", getWCommand))
    app.add_handler(CommandHandler("get_auths", getAuthsCommand))
    app.add_handler(CommandHandler("get_critical", getCriticalCommand))
    app.add_handler(CommandHandler("get_ps", getPsCommand))
    app.add_handler(CommandHandler("get_ss", getSsCommand))
    app.add_handler(CommandHandler("get_services", getServicesCommand))
    app.add_handler(CommandHandler("get_repl_logs", getReplLogsCommand))
    app.add_handler(CommandHandler("get_emails", getEmailsCommand))
    app.add_handler(CommandHandler("get_phone_numbers", getPhoneNumbersCommand))
    
    app.add_handler(convHandlerFindPhoneNumbers)
    app.add_handler(convHandlerFindEmailAddresses)
    app.add_handler(convHandlerVerifyPassword)
    app.add_handler(convHandlerGetAptList)

    # Обработчик текста
    app.add_handler(MessageHandler(filters.TEXT & ~ filters.COMMAND, echo))

    logging.info("Добавлены обработчики")

    logging.info("Запуск бота")
    app.run_polling()


if __name__ == "__main__":
    main()
