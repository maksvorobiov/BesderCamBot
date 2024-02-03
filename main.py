import telebot.async_telebot
import socket
import json
import asyncio
from datetime import datetime
import pytz
import re
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT"]
time_zone = 'Europe/Kiev' # Check it in pytz or https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568

bot = telebot.async_telebot.AsyncTeleBot(BOT_TOKEN)

reference_time = ""
alert = True

# You can turn off this filter
class IsMe(telebot.asyncio_filters.SimpleCustomFilter):
    key='is_me'
    @staticmethod
    async def check(message: telebot.types.Message):
        if message.from_user.id == int(CHAT_ID): return True
        else: return False

async def write_to_file(text):
    kiev_time = pytz.timezone(time_zone).normalize(datetime.now(tz=pytz.utc)).strftime('%Y-%m-%d %H:%M:%S')
    with open('logs.txt', 'a') as file:
        file.write(f"[{kiev_time}] {text}\n")

async def send_alarm_message(alarm_data):
    global reference_time
    serial_number = alarm_data.get('SerialID')
    alert_event = alarm_data.get('Event')
    alert_time = alarm_data.get('StartTime')
    alert_status = alarm_data.get('Status')
    current_time = re.search(r'\d+:\d+', alert_time)[0]
    if serial_number == '44098fe28501926a':
        place = 'Door'
    elif serial_number == '81752845777b8188':
        place = "Garage"
    if alert_event == "HumanDetect" and alert_status == "Start" and alert and current_time != reference_time:
        await bot.send_message(CHAT_ID,
                               f"🚨 Warning! 🚨\nPlace: *{place}*\nEvent: Human Detection\nTime: {alert_time}",
                               parse_mode='Markdown')
        reference_time = current_time
    else:
        await write_to_file(f"Place: {place}. Event: {alert_event}")

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    await write_to_file(f"Connection from {addr}")
    while True:
        data = await reader.read(1024)
        if not data:
            break
        try:
            start_json = data.find(b'{')
            if start_json != -1:
                json_data = data[start_json:].decode('utf-8')
                alarm_data = json.loads(json_data)
                await send_alarm_message(alarm_data)
        except Exception as e:
            await write_to_file(e)
    writer.close()
    await writer.wait_closed()

async def run_server(host='0.0.0.0', port=8080):
    server = await asyncio.start_server(handle_client, host, port)
    addr = server.sockets[0].getsockname()
    await write_to_file(f"Serving on {addr}")
    async with server:
        await server.serve_forever()


@bot.message_handler(commands=['start'])
async def start_command(message):
    await write_to_file(f"Somebody have started bot. Username: {message.from_user.username} "
                        f"Name: {message.from_user.first_name} ID: {message.from_user.id}")

@bot.message_handler(commands=['log'], is_me=True)
async def send_log(message):
    with open('logs.txt', 'rb') as file:
        await bot.send_document(CHAT_ID, file)

@bot.message_handler(commands=['alert_on'], is_me=True)
async def turn_on_alert(message):
    global alert
    alert = True
    await write_to_file("=====Turn ON notifications=====")
    await bot.send_message(CHAT_ID, "Notification is *ON*", parse_mode="Markdown")

@bot.message_handler(commands=['alert_off'], is_me=True)
async def turn_off_alert(message):
    global alert
    alert = False
    await write_to_file("=====Turn OFF notifications=====")
    await bot.send_message(CHAT_ID, "Notification is *OFF*", parse_mode="Markdown")

@bot.message_handler(commands=['status'], is_me=True)
async def bot_status(message):
    await bot.send_message(CHAT_ID, f"Bot is running. Sending notification set to *{alert}*", parse_mode="Markdown")

@bot.message_handler(commands=['clean_log'], is_me=True)
async def clean_logs(message):
    with open('logs.txt', 'w') as file:
        file.write("Logs")
    await bot.send_message(CHAT_ID, f"Log file is now *empty*", parse_mode="Markdown")


bot.add_custom_filter(IsMe())

async def main():
    server_task = asyncio.create_task(run_server())
    bot_task = asyncio.create_task(bot.infinity_polling(skip_pending=True))
    await asyncio.gather(server_task, bot_task)

if __name__ == '__main__':
    asyncio.run(main())
