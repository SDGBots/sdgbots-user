# SCP-079-USER - Invite and help other bots
# Copyright (C) 2019 SCP-079 <https://scp-079.org>
#
# This file is part of SCP-079-USER.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from struct import pack
from typing import Iterable, List, Optional, Union

from pyrogram import Chat, ChatMember, Client, InlineKeyboardMarkup, Message
from pyrogram.api.functions.channels import DeleteUserHistory, ReadHistory
from pyrogram.api.functions.messages import GetCommonChats, GetWebPagePreview, ReadMentions
from pyrogram.api.types import FileLocation, MessageMediaPhoto, MessageMediaWebPage, Photo, PhotoSize, WebPage
from pyrogram.api.types import InputPeerUser, InputPeerChannel
from pyrogram.client.ext.utils import encode
from pyrogram.errors import ChannelInvalid, ChannelPrivate, FloodWait, PeerIdInvalid

from .. import glovar
from .etc import delay, get_text, wait_flood

# Enable logging
logger = logging.getLogger(__name__)


def delete_messages(client: Client, cid: int, mids: Iterable[int]) -> Optional[bool]:
    # Delete some messages
    result = None
    try:
        mids = list(mids)
        mids_list = [mids[i:i + 100] for i in range(0, len(mids), 100)]
        for mids in mids_list:
            try:
                flood_wait = True
                while flood_wait:
                    flood_wait = False
                    try:
                        result = client.delete_messages(chat_id=cid, message_ids=mids)
                    except FloodWait as e:
                        flood_wait = True
                        wait_flood(e)
            except Exception as e:
                logger.warning(f"Delete message in for loop error: {e}", exc_info=True)
    except Exception as e:
        logger.warning(f"Delete messages in {cid} error: {e}", exc_info=True)

    return result


def delete_all_messages(client: Client, gid: int, uid: int) -> bool:
    # Delete a user's all messages in a group
    try:
        group_id = resolve_peer(client, gid)
        user_id = resolve_peer(client, uid)
        if group_id and user_id:
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    client.send(DeleteUserHistory(channel=group_id, user_id=user_id))
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)

        return True
    except Exception as e:
        logger.warning('Delete user all message error: %s', e)

    return False


def get_admins(client: Client, cid: int) -> Optional[Union[bool, List[ChatMember]]]:
    # Get a group's admins
    result = None
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                result = client.get_chat_members(chat_id=cid, filter="administrators")
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)
            except (PeerIdInvalid, ChannelInvalid, ChannelPrivate):
                return False

        result = result.chat_members
    except Exception as e:
        logger.warning(f"Get admin ids in {cid} error: {e}", exc_info=True)

    return result


def get_common_chats(client: Client, uid: int) -> Optional[List[Chat]]:
    # Get the common groups with a user
    result = None
    try:
        user_id = resolve_peer(client, uid)
        if user_id:
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    chats = client.send(GetCommonChats(
                        user_id=user_id,
                        max_id=0,
                        limit=len(glovar.configs))
                    )
                    result = chats.chats
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)
    except Exception as e:
        logger.warning(f"Get common chats error: {e}", exc_info=True)

    return result


def get_group_info(client: Client, chat: Union[int, Chat]) -> (str, str):
    # Get a group's name and link
    group_name = "Unknown Group"
    group_link = glovar.default_group_link
    try:
        if isinstance(chat, int):
            result = None
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    result = client.get_chat(chat_id=chat)
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)
                except Exception as e:
                    logger.warning(f"Get chat {chat} error: {e}")

            chat = result

        if chat.title:
            group_name = chat.title

        if chat.username:
            group_link = "https://t.me/" + chat.username
    except Exception as e:
        logger.info('Get group info error: %s', e)

    return group_name, group_link


def get_preview(client: Client, message: Message) -> (dict, str):
    # Get message's preview
    preview = {
        "text": None,
        "file_id": None
    }
    url = ""
    try:
        if should_preview(message):
            result = None
            message_text = get_text(message)
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    result = client.send(GetWebPagePreview(message=message_text))
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)

            if result:
                photo = None
                if isinstance(result, MessageMediaWebPage):
                    web_page = result.webpage
                    if isinstance(web_page, WebPage):
                        text = ""
                        if web_page.url:
                            url = web_page.url

                        if web_page.display_url:
                            text += web_page.display_url + "\n\n"

                        if web_page.site_name:
                            text += web_page.site_name + "\n\n"

                        if web_page.title:
                            text += web_page.title + "\n\n"

                        if web_page.description:
                            text += web_page.description + "\n\n"

                        preview["text"] = text.strip()
                        if web_page.photo:
                            if isinstance(web_page.photo, Photo):
                                photo = web_page.photo
                elif isinstance(result, MessageMediaPhoto):
                    media = result.photo
                    if isinstance(media, Photo):
                        photo = media

                if photo:
                    size = photo.sizes[-1]
                    if isinstance(size, PhotoSize):
                        file_size = size.size
                        if file_size < glovar.image_size:
                            loc = size.location
                            if isinstance(loc, FileLocation):
                                file_id = encode(
                                    pack(
                                        "<iiqqqqi",
                                        2,
                                        loc.dc_id,
                                        photo.id,
                                        photo.access_hash,
                                        loc.volume_id,
                                        loc.secret,
                                        loc.local_id
                                    )
                                )
                                preview["file_id"] = file_id
    except Exception as e:
        logger.warning(f"Get preview error: {e}", exc_info=True)

    return preview, url


def kick_chat_member(client: Client, cid: int, uid: int) -> Optional[Union[bool, Message]]:
    # Kick a chat member in a group
    result = None
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                result = client.kick_chat_member(chat_id=cid, user_id=uid)
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)
    except Exception as e:
        logger.warning(f"Kick chat member {uid} in {cid} error: {e}", exc_info=True)

    return result


def leave_chat(client: Client, cid: int) -> bool:
    # Leave a channel
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                client.leave_chat(chat_id=cid)
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)

        return True
    except Exception as e:
        logger.warning(f"Leave chat {cid} error: {e}")

    return False


def mark_as_read(client: Client, cid: int, read_type: str) -> bool:
    # Mark a channel as read
    try:
        peer = resolve_peer(client, cid)
        if peer:
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    if read_type == "mention":
                        client.send(ReadMentions(peer=peer))
                    elif read_type == "message":
                        client.send(ReadHistory(channel=peer, max_id=0))
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)

            return True
    except Exception as e:
        logger.warning(f"Mark as read error: {e}", exc_info=True)

    return False


def resolve_peer(client: Client, pid: int) -> Optional[Union[InputPeerChannel, InputPeerUser]]:
    # Get an input peer by id
    result = None
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                result = client.resolve_peer(pid)
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)
    except Exception as e:
        logger.warning(f"Resolve peer error: {e}", exc_info=True)

    return result


def send_document(client: Client, cid: int, file: str, text: str = None, mid: int = None,
                  markup: InlineKeyboardMarkup = None) -> Optional[Union[bool, Message]]:
    # Send a document to a chat
    result = None
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                result = client.send_document(
                    chat_id=cid,
                    document=file,
                    caption=text,
                    reply_to_message_id=mid,
                    reply_markup=markup
                )
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)
            except (PeerIdInvalid, ChannelInvalid, ChannelPrivate):
                return False
    except Exception as e:
        logger.warning(f"Send document to {cid} error: {e}", exec_info=True)

    return result


def send_message(client: Client, cid: int, text: str, mid: int = None,
                 markup: InlineKeyboardMarkup = None) -> Optional[Union[bool, Message]]:
    # Send a message to a chat
    result = None
    try:
        if text.strip():
            text_list = [text[i:i + 4096] for i in range(0, len(text), 4096)]
            for text_unit in text_list:
                flood_wait = True
                while flood_wait:
                    flood_wait = False
                    try:
                        result = client.send_message(
                            chat_id=cid,
                            text=text_unit,
                            disable_web_page_preview=True,
                            reply_to_message_id=mid,
                            reply_markup=markup
                        )
                    except FloodWait as e:
                        flood_wait = True
                        wait_flood(e)
                    except (PeerIdInvalid, ChannelInvalid, ChannelPrivate):
                        return False
    except Exception as e:
        logger.warning(f"Send message to {cid} error: {e}", exc_info=True)

    return result


def send_photo(client: Client, cid: int, photo: str, caption: str = None, mid: int = None,
               markup: InlineKeyboardMarkup = None) -> Optional[Union[bool, Message]]:
    # Send a photo to a chat
    result = None
    try:
        if photo.strip():
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    result = client.send_photo(
                        chat_id=cid,
                        photo=photo,
                        caption=caption,
                        reply_to_message_id=mid,
                        reply_markup=markup
                    )
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)
                except (PeerIdInvalid, ChannelInvalid, ChannelPrivate):
                    return False
    except Exception as e:
        logger.warning(f"Send photo to {cid} error: {e}", exc_info=True)

    return result


def send_report_message(secs: int, client: Client, cid: int, text: str, mid: int = None,
                        markup: InlineKeyboardMarkup = None) -> Optional[Message]:
    # Send a message that will be auto deleted to a chat
    result = None
    try:
        if text.strip():
            flood_wait = True
            while flood_wait:
                flood_wait = False
                try:
                    result = client.send_message(
                        chat_id=cid,
                        text=text,
                        disable_web_page_preview=True,
                        reply_to_message_id=mid,
                        reply_markup=markup
                    )
                except FloodWait as e:
                    flood_wait = True
                    wait_flood(e)

            mid = result.message_id
            mids = [mid]
            delay(secs, delete_messages, [client, cid, mids])
    except Exception as e:
        logger.warning(f"Send message to {cid} error: {e}", exc_info=True)

    return result


def should_preview(message: Message) -> bool:
    # Check if the message should be previewed
    if message.entities or message.caption_entities:
        if message.entities:
            entities = message.entities
        else:
            entities = message.caption_entities

        for en in entities:
            if en.type in ["url", "text_link"]:
                return True

    return False


def unban_chat_member(client: Client, cid: int, uid: int) -> Optional[bool]:
    # Unban a user in a group
    result = None
    try:
        flood_wait = True
        while flood_wait:
            flood_wait = False
            try:
                result = client.unban_chat_member(chat_id=cid, user_id=uid)
            except FloodWait as e:
                flood_wait = True
                wait_flood(e)
    except Exception as e:
        logger.warning(f"Unban chat member {uid} in {cid} error: {e}")

    return result
