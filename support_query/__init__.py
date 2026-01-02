import json
import re
import os
import time
from nonebot import get_bot
from .create_img import general_img
from .accurateassis import accurateassis
from .support_tools import (
    get_scene_config,
    find_character_by_name,
    get_qq_id,
    parse_support_units,
    check_character_in_support,
    change_support_unit,
    remove_support_unit,
    COOLDOWN_TIME
)
from .task_manager import task_manager
from ..login import query
from ..util.text2img import image_draw
from ..util.tools import load_config, DATA_PATH
from hoshino import Service, priv
from hoshino.typing import CQEvent, NoticeSession, MessageSegment
from hoshino.util import pic2b64
from hoshino.modules.convert2img.convert2img import grid2imgb64

help_text = '''
【换助战】
格式：(换|挂|上)(场景(可不填))(助战) 角色名 (@目标用户(可不填))
场景：地下城/公会战(会战)/露娜塔/关卡(活动)，不填默认为公会战
示例：换助战优衣 / 挂地下城助战妹法 / 上深域助战克总 @目标用户

• 不@目标用户时：
  - 公会战：换出刀监控人的助战
  - 地下城&露娜塔&关卡&深域：换自己的助战
• @目标用户时，换目标用户的助战：
  - 管理员：无需确认，直接执行
  - 普通用户：需要对方回复"同意"，以防顶号（3分钟内有效）
• 同意/拒绝：同意或拒绝别人发起的换助战请求

注意：角色如在其他位置助战中，会自动取下后放到目标位置
========================================================
【刷新box缓存】会顶号，请注意，机器人自动上号记录你的box
【box查询+角色名字】（@别人可以查别人，角色名输入【所有】则都查）
【绑定本群公会】将自己绑定在这个群
【删除本群公会绑定】将自己踢出公会（管理可以at别人实现踢人效果）
【公会box查询+角色名字】查询绑定公会的玩家的box，不支持输入所有（卡不死你）
【刷新助战缓存】会顶号，请注意，机器人自动上号记录公会助战
【精确助战+角色名字】（角色名输入【所有】则都查）
【绑定账号+账号+密码】加号为空格(加好友私聊)
'''.strip()

sv = Service(
    name="精准助战",  # 功能名
    visible=True,  # 可见性
    enable_on_default=True,  # 默认启用
    help_=help_text,  # 帮助说明
)

class SupportMonitor(object):
    def __init__(self):
        self.qid = 0
        self.nickname = ""
        self.monitor_client = None
    
    async def add_monitor(self, qid, group_id, bot):
        monitor_client, nickname = await self.user_login(qid, group_id, bot)
        if monitor_client:
            self.qid = qid # 助战人的qq号
            self.nickname = nickname # 助战人的昵称
            self.monitor_client = monitor_client # 助战人的登录实例
            return self.nickname
        else:
            return None

    async def user_login(self, qid, group_id, bot):
        acccountinfo = await load_config(os.path.join(DATA_PATH, 'account', f'{qid}.json'))
        if acccountinfo != []:
            monitor_client = await query(acccountinfo)
            user_info = await bot.get_group_member_info(group_id = group_id, user_id = qid)
            nickname = user_info["card"] or user_info["nickname"]
            return monitor_client, nickname

info_path = os.path.join(DATA_PATH, "support_query")

async def get_support_list(info, acccountinfo, qq_id):
    client = await query(acccountinfo)
    load_index = await client.callapi('/load/index', {'carrier': 'OPPO'})
    home_index = await client.callapi('/home/index', {'message_id': 1, 'tips_id_list': [], 'is_first': 1, 'gold_history': 0})
    if info == 'support_query':
        clan_id = home_index['user_clan']['clan_id']
        support_list = await client.callapi('/clan_battle/support_unit_list_2', {"clan_id": clan_id})
        return support_list
    if info == 'self_query':
        return load_index

def get_info(file, name, isSelf = False):
    try:
        A = accurateassis(file) # 输入json的路径
    except:
        return '没有缓存,请先根据指令进行缓存', False
    check = A.translatename2id(name) # 输入要查询角色的名称
    if check:
        return check, False
    all_info = A.serchassis() if not isSelf else A.user_card()
    if len(all_info) == 0:
        return '没有找到该角色', False
    return all_info, True

@sv.on_fullmatch('查box帮助', '助战帮助')
async def query_help(bot, ev: CQEvent):
    img = image_draw(help_text)
    await bot.send(ev, img)

@sv.on_prefix('精准助战','精确助战')
async def query_clanbattle_support(bot, ev: CQEvent):
    group_id = ev.group_id
    file = os.path.join(info_path,'group',f'{group_id}','support.json')
    name = ev.message.extract_plain_text().strip()
    all_info,check = get_info(file,name)
    if not check:
        await bot.send(ev, all_info)
        return
    images = await general_img(all_info)
    result = pic2b64(images)
    msg = str(MessageSegment.image(result))
    await bot.send(ev, msg)

@sv.on_fullmatch('刷新助战缓存')
async def create_support_cache(bot, ev: CQEvent):
    qq_id = ev.user_id
    acccountinfo = await load_config(os.path.join(DATA_PATH, 'account', f'{qq_id}.json'))
    if acccountinfo != []:
        support_list = await get_support_list('support_query', acccountinfo, qq_id)
        if "server_error" in support_list:
            await bot.send(ev, "可能现在不是会战的时候或者网络异常")
            return
        group_id = ev.group_id
        os.makedirs(os.path.join(info_path, 'group', f'{group_id}'), exist_ok=True)
        with open(os.path.join(info_path,'group',f'{group_id}','support.json'), 'w', encoding='utf-8') as f:
            json.dump(support_list, f, ensure_ascii=False)
        await bot.send(ev, "刷新成功")
    else:
        await bot.send(ev, "你没有绑定过账号")

# 刷新自己的助战列表，显示自己指定助战的详细信息
async def refreshAndShowSupportInfo(bot, ev, client, cname, qq_id):
    # 刷新自己的box缓存，写入文件
    index_infos = await client.callapi('/load/index', {'carrier': 'OPPO'})
    if "server_error" in index_infos:
        await bot.send(ev, "网络异常")
        return
    print(index_infos)

    # 如果当前账号没有对应路径和文件，创建文件夹和文件
    try:
        os.makedirs(os.path.join(info_path, 'user', f'{qq_id}'), exist_ok=True)
        with open(os.path.join(info_path, 'user', f'{qq_id}', 'self.json'), 'w', encoding='utf-8') as f:
            json.dump(index_infos, f, ensure_ascii=False)
    except:
        await bot.send(ev, "无法将box信息写入文件！")
        raise
    
    # 读取文件，找到目标角色信息
    all_info, check = get_info(os.path.join(info_path, 'user', f'{qq_id}', 'self.json'), cname, True)
    if not check:
        await bot.send(ev, all_info)
        return
    
    # 绘制图片输出
    try:
        images = await general_img(all_info)
        result = pic2b64(images)
        msg = str(MessageSegment.image(result))
        await bot.send(ev, msg)
    except:
        await bot.send(ev, "生成助战角色配置图片失败！")
        raise


# 执行换助战的核心逻辑
async def change_support(bot, ev, scene: str, chara_id: int, chara_name: str, qq_id: int, group_id: int):
    """
    执行换助战的核心逻辑
    
    Args:
        bot: bot实例
        ev: 事件对象
        scene: 场景（地下城/公会战等）
        chara_id: 角色ID
        chara_name: 角色名称
        qq_id: 目标用户QQ号
        group_id: 群号
    """
    # 获取目标用户的昵称
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=qq_id)
    nickname = user_info["card"] or user_info["nickname"]
    # 判断是否为自己的助战
    is_self = qq_id == ev.user_id
    await bot.send(ev, f'正在{"您" if is_self else nickname}的BOX中寻找该角色...')
    
    # 登录账号
    account_info = await load_config(os.path.join(DATA_PATH, 'account', f'{qq_id}.json'))
    if not account_info:
        await bot.send(ev, '未找到账号信息')
        return
    # 获取客户端实例
    client = await query(account_info)
    
    # 获取助战位信息
    support_data = await client.callapi('/support_unit/get_setting', {})
    clan_dungeon_units = support_data['clan_support_units']
    friend_units_data = support_data['friend_support_units']
    all_support_units = clan_dungeon_units + friend_units_data
    # 助战位信息格式化
    units_dict = parse_support_units(clan_dungeon_units, friend_units_data)
    # 检查角色是否已在助战中
    is_in_support, pos_name, old_support_type, old_position = check_character_in_support(all_support_units, chara_id)
    if is_in_support:
        await bot.send(ev, f'检测到角色已在{pos_name}助战中，正在取下...')
        # 先取下原位置的角色
        remove_success = await remove_support_unit(client, old_support_type, old_position)
        if not remove_success:
            await bot.send(ev, '取下角色失败')
            return
        await bot.send(ev, '已取下，正在放置到目标位置...')
    
    config = get_scene_config(scene)
    target_units = units_dict[config['units_key']]
    units_name = config['display_name']
    # 检查目标助战位
    for index, unit in enumerate(target_units):
        # 是否超过30分钟冷却
        time_diff = int(time.time() - unit['support_start_time'])
        if time_diff > COOLDOWN_TIME:
            unit_id = int(str(chara_id) + '01')
            position = index + config['position_offset']
            # 更换助战角色
            success = await change_support_unit(client, config['support_type'], position, unit_id)
            if not success:
                await bot.send(ev, '操作失败')
                return
            # 发送提示消息
            await bot.send(ev, f'已将{nickname}的{chara_name}挂至{units_name}{index + 1}号助战位中')
            # 发送助战角色信息图片
            await refreshAndShowSupportInfo(bot, ev, client, chara_name, qq_id)
            return
    
    # 助战位都未超过30分钟的提示
    await bot.send(ev, '操作失败！可能是两个助战位都未超过30分钟')


@sv.on_rex(r"^(上|挂|换|切换|更换|修改)(地下城|公会|公会战|会战|工会战|工会|露娜|露娜塔|关卡|活动|深域|深渊)?(支援|助战) ?(\S+)$")
async def change_support_command(bot, ev: CQEvent):
    # 获取助战场景（地下城/会战/露娜塔/关卡/深域）
    match = ev['match']
    scene = match.group(2) if match.group(2) else "公会战"
    # 获取指令中的角色名/外号
    target_chara = match.group(4).strip()
    
    # 寻找角色ID和正式名称
    chara_id, chara_name = find_character_by_name(target_chara)
    if chara_id == 0:
        await bot.send(ev, f'未找到{target_chara}！请使用其他名称重试')
        return
    
    await bot.send(ev, f'已确定您说的是{chara_name}')
    
    # 获取 群号 和 目标用户的QQ号
    group_id = ev.group_id
    qq_id, error_msg = get_qq_id(ev, scene, group_id)
    
    # 检查是否获取到有效的QQ号
    if qq_id == 0:
        await bot.send(ev, f'获取目标用户失败：{error_msg}')
        return
    
    # 判断是否@了别人
    is_at = len(ev.message) == 3 and ev.message[0].type == 'text' and ev.message[1].type == 'at'
    
    if is_at:
        # @了别人，需要检查权限
        operator_qq = ev.user_id
        
        # 检查操作者是否是管理员
        if priv.check_priv(ev, priv.ADMIN):
            # 管理员直接执行
            await bot.send(ev, '检测到管理员权限，直接执行换助战操作')
            await change_support(bot, ev, scene, chara_id, chara_name, qq_id, group_id)
        else:
            # 非管理员，需要目标用户确认
            # 先清理过期任务
            task_manager.clear_expired_tasks()
            
            # 创建任务
            task = task_manager.add_task(qq_id, chara_id, chara_name, scene, group_id, operator_qq)
            
            # 获取操作者和目标用户的昵称
            operator_info = await bot.get_group_member_info(group_id=group_id, user_id=operator_qq)
            operator_name = operator_info["card"] or operator_info["nickname"]
            
            target_info = await bot.get_group_member_info(group_id=group_id, user_id=qq_id)
            target_name = target_info["card"] or target_info["nickname"]
            
            await bot.send(ev, 
                f'{operator_name}请求将{target_name}的{chara_name}更换到{scene}助战位\n'
                f'[CQ:at,qq={qq_id}] 请在3分钟内回复"同意"或"拒绝"')
    else:
        # 没有@别人，换自己的助战，直接执行
        await change_support(bot, ev, scene, chara_id, chara_name, qq_id, group_id)


@sv.on_fullmatch('同意')
async def confirm_change_support(bot, ev: CQEvent):
    """处理用户确认换助战的请求"""
    qq_id = ev.user_id
    group_id = ev.group_id
    
    # 先清理过期任务
    task_manager.clear_expired_tasks()
    
    # 查找该用户的待确认任务
    task = task_manager.get_task(qq_id)
    
    if not task:
        await bot.send(ev, '没有找到待确认的换助战任务')
        return
    
    # 检查群号是否一致
    if task.group_id != group_id:
        await bot.send(ev, '该任务不是在本群发起的')
        return
    
    # 检查是否过期
    if task.is_expired(180):
        task_manager.remove_task(qq_id)
        await bot.send(ev, '任务已过期（超过3分钟），请重新发起请求')
        return
    
    # 获取操作者昵称
    operator_info = await bot.get_group_member_info(group_id=group_id, user_id=task.operator_qq)
    operator_name = operator_info["card"] or operator_info["nickname"]
    
    # 任务有效，执行换助战操作
    await bot.send(ev, f'已确认{operator_name}的请求，开始执行换助战操作')
    
    # 删除任务
    task_manager.remove_task(qq_id)
    
    # 执行换助战
    await change_support(bot, ev, task.scene, task.chara_id, task.chara_name, qq_id, group_id)


@sv.on_fullmatch('拒绝')
async def reject_change_support(bot, ev: CQEvent):
    """处理用户拒绝换助战的请求"""
    qq_id = ev.user_id
    
    # 查找该用户的待确认任务
    task = task_manager.get_task(qq_id)
    
    if not task:
        await bot.send(ev, '没有找到待确认的换助战任务')
        return
    
    # 删除任务
    task_manager.remove_task(qq_id)
    await bot.send(ev, '已取消换助战请求')


@sv.on_prefix('box查询')
async def query_clanbattle_support(bot, ev: CQEvent):
    qq_id = ev.user_id
    name = ev.message.extract_plain_text().strip()
    content = ev.raw_message
    if '[CQ:at,qq=' in content:
        qq_id = re.findall(r"CQ:at,qq=([0-9]+)",content)[0]
    all_info,check = get_info(os.path.join(info_path, 'user', f'{qq_id}','self.json'),name,True)
    if not check:
        await bot.send(ev, all_info)
        return
    images = await general_img(all_info)
    result = pic2b64(images)
    msg = str(MessageSegment.image(result))
    await bot.send(ev, msg)

@sv.on_fullmatch('刷新box缓存')
async def create_self_cache(bot, ev: CQEvent):
    qq_id = ev.user_id
    os.makedirs(os.path.join(info_path, 'user', f'{qq_id}'), exist_ok=True)
    acccountinfo = await load_config(os.path.join(DATA_PATH, 'account', f'{qq_id}.json'))
    if acccountinfo != []:
        support_list = await get_support_list('self_query', acccountinfo, qq_id)
        if "server_error" in support_list:
            await bot.send(ev, "网络异常")
            return
        with open(os.path.join(info_path, 'user', f'{qq_id}','self.json'), 'w', encoding='utf-8') as f:
            json.dump(support_list, f, ensure_ascii=False)
        await bot.send(ev, "刷新成功")
    else:
        await bot.send(ev, "你没有绑定过账号")

@sv.on_fullmatch('绑定本群公会')
async def create_self_cache(bot, ev: CQEvent):
    qq_id = ev.user_id
    group_id = ev.group_id
    acccountinfo = await load_config(os.path.join(DATA_PATH, 'account', f'{qq_id}.json'))
    if acccountinfo != []:
        os.makedirs(os.path.join(info_path, 'group', f'{group_id}'),exist_ok=True)
        file = os.path.join(info_path, 'group', f'{group_id}','player.json')
        player_list = await load_config(file)
        if qq_id not in player_list:
            player_list.append(qq_id)
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(player_list, f, ensure_ascii=False)
        await bot.send(ev, "绑定本群公会成功")
    else:
        await bot.send(ev, "你没有绑定过账号")

@sv.on_prefix('删除本群公会绑定')
async def create_self_cache(bot, ev: CQEvent):
    if len(ev.message) == 1 and ev.message[0].type == 'text' and not ev.message[0].data['text']:
        qq_id = ev.user_id
    elif ev.message[0].type == 'at':
        if not priv.check_priv(ev, priv.ADMIN):
            msg = '很抱歉您没有权限进行此操作，该操作仅管理员'
            await bot.send(ev, msg)
            return
        qq_id = int(ev.message[0].data['qq'])
    group_id = ev.group_id
    os.makedirs(os.path.join(info_path, 'group', f'{group_id}'),exist_ok=True)
    file = os.path.join(info_path, 'group', f'{group_id}','player.json')
    player_list = await load_config(file)
    if qq_id in player_list:
        player_list.remove(qq_id)
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(player_list, f, ensure_ascii=False)
    await bot.send(ev, "删除本群公会绑定成功")

@sv.on_prefix('公会box查询')
async def query_clanbattle_support(bot, ev: CQEvent):
    clan_info = []
    name = ev.message.extract_plain_text().strip()
    if name == '所有':
        await bot.send(ev, '爬爬，你想累死我')
        return
    group_id = ev.group_id
    player_list = await load_config(os.path.join(info_path, 'group', f'{group_id}','player.json'))
    if player_list != []:
        for qq_id in player_list:
            file = os.path.join(info_path, 'user', f'{qq_id}','self.json')
            all_info,check = get_info(file,name,True)
            if check:
                clan_info += all_info
    if len(clan_info) == 0:
        await bot.send(ev, '没有找到该角色')
        return
    images = await general_img(clan_info)
    result = pic2b64(images)
    msg = str(MessageSegment.image(result))
    await bot.send(ev, msg)

@sv.on_fullmatch('生成pcr简介')
async def query_clanbattle_support(bot, ev: CQEvent):
    qq_id = ev.user_id
    try:
        A = accurateassis(os.path.join(info_path, 'user', f'{qq_id}','self.json'))
    except:
        await bot.send(ev, '你没有缓存')
        return
    title, info = A.user_info()
    img = grid2imgb64(info,title)
    await bot.send(ev, img)

@sv.on_notice('group_decrease')
async def leave_notice(session: NoticeSession):
    uid = str(session.ctx['user_id'])
    gid = str(session.ctx['group_id'])
    bot = get_bot()
    os.makedirs(os.path.join(info_path, 'group', f'{gid}'), exist_ok=True)
    file = os.path.join(info_path, 'group', f'{gid}','player.json')
    player_list = await load_config(file)
    if uid in player_list:
        player_list.remove(uid)
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(player_list, f, ensure_ascii=False)
        await bot.send_group_msg(group_id = int(gid),message = f'{uid}退群了，已自动删除其绑定在本群的公会绑定')
