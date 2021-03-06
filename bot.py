import math
import io
import time
import json
import sys
from datetime import datetime
from os import environ
from PIL import Image, ImageFont, ImageDraw
from openwa.helper import convert_to_base64
from openwa.objects.message import Message, MediaMessage
from openwa.objects.chat import Chat
from openwa import WhatsAPIDriver
SPAM_TIME = 30
SPAM_WARN = 16
SPAM_MAX = 20
RETURN_TIME = 60  # how long can someone be out, in seconds
REMOVE_CONSENSUS = 5  # requires n people to agree for removal
REMOVE_VALIDITY_TIME = 30 * 60  # asking for a remove is valid for 30 minutes


driver = WhatsAPIDriver(
    client=environ["CLIENT"],
    profile=environ["PROFILE"],
    headless=True)
driver.wait_for_login()
time.sleep(1)
print("Bot started")

memory = {}
try:
    with open("memory.json", "r") as f:
        memory = json.load(f)
except BaseException:
    pass


def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f)


save_memory()


def draw_text(img, text, top=True):
    font = ImageFont.truetype("./font.ttf", 80)
    draw = ImageDraw.Draw(img)
    draw.text(
        (256, 5 if top else 507), text, font=font, fill=(
            255, 255, 255), stroke_width=5, stroke_fill=(
            0, 0, 0), anchor=(
                "mt" if top else "mb"), direction="rtl")


def remove_and_remember(chat, author_id):
    if "add_back" not in memory:
        memory["add_back"] = []
    driver.remove_participant_group(chat.id, author_id)
    memory["add_back"].append((time.time() + RETURN_TIME, chat.id, author_id))
    save_memory()


chat_state = {}


def got_message(message):
    # log who sent this
    global memory, chat_state
    msg = message.messages[0]
    msg_author = msg.sender.id

    if message.chat.id not in chat_state:
        chat_state[message.chat.id] = {"message_times": {}, "remove_times": {}}

    c_st = chat_state[message.chat.id]

    # check for spam
    if msg_author in c_st["message_times"]:
        c_st["message_times"][msg_author] = [
            x for x in c_st["message_times"][msg_author] if (
                time.time() - x) < SPAM_TIME]
        c_st["message_times"][msg_author] += [time.time()]
        msg_cnt = len(c_st["message_times"][msg_author])
        if msg_cnt >= SPAM_MAX:
            # remove from group
            try:
                remove_and_remember(message.chat, msg_author)
            except:
                pass
        elif msg_cnt >= SPAM_WARN:
            # warn for spam
            driver.chat_send_message(msg.chat_id, "די להספים! " +
                                     f"({msg_cnt}/{SPAM_MAX})")
    else:
        c_st["message_times"][msg_author] = [time.time()]

    if isinstance(msg, MediaMessage):
        command = msg.caption
    else:
        command = msg.content

    if not command.startswith("מישה "):
        return
    command = command[5:]
    command_words = command.split(" ")
    command_first_word = command_words[0]

    if command_first_word == "סטיקר":
        if isinstance(msg, MediaMessage):
            img = Image.open(driver.download_media(msg, force_download=True))
            # Resize image
            if img.width > img.height:
                result_width = 512
                result_height = math.floor(img.height * (512 / img.width))
            else:
                result_height = 512
                result_width = math.floor(img.width * (512 / img.height))
            resized = img.resize((result_width, result_height)).convert("RGBA")
            sticker_img = Image.new("RGBA", (512, 512))
            sticker_img.paste(
                resized,
                ((512 - result_width) // 2,
                 (512 - result_height) // 2))
            # Potentially add text
            semicolon_seperated = " ".join(command_words[1:]).split(";")
            if len(semicolon_seperated) != 0 and semicolon_seperated[0] != "":
                # draw text
                draw_text(sticker_img, semicolon_seperated[0], top=True)
                if len(semicolon_seperated) >= 2:
                    draw_text(sticker_img, semicolon_seperated[1], top=False)
            # Send result image
            webp_img = io.BytesIO()
            sticker_img.save(webp_img, "webp")
            webp_img.seek(0)
            img_base_64 = convert_to_base64(webp_img, is_thumbnail=True)
            return driver.wapi_functions.sendImageAsSticker(
                img_base_64, msg.chat_id, {})
        else:
            driver.chat_send_message(msg.chat_id, "אין פה תמונה")
    elif command_first_word == "להוציא":
        remove_id = command_words[1][1:] + "@c.us"
        # save a tuple of timestamp and who wants to remove remove_id
        # in c_st["remove_times"][remove_id]
        if remove_id in c_st["remove_times"]:
            # remove historic data
            c_st["remove_times"][remove_id] = [
                x for x in c_st["remove_times"][remove_id] if (
                    time.time() - x[0]) < REMOVE_VALIDITY_TIME]

            # check for double-voting
            for x in c_st["remove_times"][remove_id]:
                if x[1] == msg_author:
                    driver.chat_send_message(msg.chat_id, "הצבעת פעמיים")
                    return
            # add this vote
            c_st["remove_times"][remove_id] += [(time.time(), msg_author)]
            rm_cnt = len(c_st["remove_times"][remove_id])
            driver.chat_send_message(msg.chat_id,
                                     f"הוצאה {rm_cnt}/{REMOVE_CONSENSUS}")
            if rm_cnt >= REMOVE_CONSENSUS:
                # remove from group
                try:
                    del c_st["remove_times"][remove_id]
                    remove_and_remember(message.chat, remove_id)
                except:
                    pass
        else:
            # add first vote
            c_st["remove_times"][remove_id] = [(time.time(), msg_author)]
            driver.chat_send_message(msg.chat_id,
                                     f"הוצאה 1/{REMOVE_CONSENSUS}")
    elif command_first_word == "מידע":
        driver.chat_send_message(msg.chat_id, """היי אני הבוט של מישה!
הפקודות שלי הן:
1. מישה סטיקר טקסט עליון;טקסט תחתון
""")


while True:
    unread_messages = driver.get_unread()
    # check if we need to return someone
    new_add_back = []
    changed_add_back = False
    if "add_back" in memory:
        for x in memory["add_back"]:
            if x[0] < time.time():
                # add back
                print("add back", x)
                try:
                    driver.add_participant_group(x[1], x[2])
                except:
                    pass
                changed_add_back = True
            else:
                new_add_back.append(x)

    if changed_add_back:
        memory["add_back"] = new_add_back
        save_memory()

    for message in unread_messages:
        try:
            got_message(message)
        except Exception as e:
            print("ERROR", repr(e))
